/*
 * layercam-media: the LayerCam camera, the ISP and the hardware encoders,
 * driven one command per line on stdin by the Python service
 * (layercam/capture.py has the protocol).
 *
 *   layercam-media [--iq DIR] [--flip 0-3] [--width W --height H] [--fps N]
 *       live mode: SC3336 -> rkaiq ISP -> VI channel 0 (NV12, scaled by the
 *       ISP to W x H: 1920x1080 by default, 2304x1296 the full sensor) -> on
 *       request JPEG (VENC 0) or one more H.264 frame (VENC 1) appended to a
 *       file.  Starts asleep (ISP and VI stopped, sensor in standby): the
 *       service wakes it for pictures and prints (heat: sim/thermal.md).
 *
 *   layercam-media --encode-jpegs LIST OUT.h264 [--fps N] [--qp N]
 *       offline: every JPEG named in LIST (one path per line) decoded with
 *       libjpeg and encoded to H.264 by the hardware encoder; prints one
 *       "FRAME offset size key" line per frame.  Needs HAVE_LIBJPEG.
 *
 * Written against the Luckfox Pico SDK's rockit MPI (media/rockit, the
 * headers luckfox_pico_rkmpi_example ships) and rkaiq uAPI2, following
 * luckfox_pico_rkmpi_example (luckfox_mpi.cc: vi_dev_init, vi_chn_init,
 * venc_init) and the SDK's simple_vi_bind_venc_jpeg.c and
 * sample_comm_isp.c.  NOT YET COMPILED FOR OR RUN ON THE CAMERA: it has
 * only been syntax-checked on a PC against those headers.
 */
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#include "rk_aiq_user_api2_ae.h"
#include "rk_aiq_user_api2_imgproc.h"
#include "rk_aiq_user_api2_sysctl.h"
#include "rk_comm_venc.h"
#include "rk_comm_vi.h"
#include "rk_mpi_mb.h"
#include "rk_mpi_sys.h"
#include "rk_mpi_venc.h"
#include "rk_mpi_vi.h"

#ifdef HAVE_LIBJPEG
#include <jpeglib.h>
#endif

#define VI_PIPE 0
#define VI_CHN 0
#define VENC_JPEG 0
#define VENC_H264 1
#define VI_DEPTH 2 /* frames the VI channel queues for us */

static rk_aiq_sys_ctx_t *aiq;
static int width = 1920, height = 1080; /* SC3336 is 2304 x 1296 (16:9) at 30 or 25 fps */
static int awake;
static int video_fd = -1;
static int video_on;
static unsigned frame_no;

static void reply(const char *fmt, ...) __attribute__((format(printf, 1, 2)));
static void reply(const char *fmt, ...) {
	va_list ap;
	va_start(ap, fmt);
	vfprintf(stdout, fmt, ap);
	va_end(ap);
	fputc('\n', stdout);
	fflush(stdout);
}

static RK_U64 now_us(void) {
	struct timespec t;
	clock_gettime(CLOCK_MONOTONIC, &t);
	return (RK_U64)t.tv_sec * 1000000 + t.tv_nsec / 1000;
}

/* ------------------------------------------------------------------ ISP */
static int isp_init(const char *iq_dir) {
	rk_aiq_static_info_t info;
	/* must be set before init (sample_comm_isp.c) */
	setenv("HDR_MODE", "0", 1);
	if (rk_aiq_uapi2_sysctl_enumStaticMetasByPhyId(0, &info) != XCAM_RETURN_NO_ERROR)
		return -1;
	aiq = rk_aiq_uapi2_sysctl_init(info.sensor_info.sensor_name, iq_dir, NULL, NULL);
	return aiq ? 0 : -1;
}

/* prepare + start; after a stop the uAPI wants both again (sysctl.h) */
static int isp_run(int flip) {
	if (rk_aiq_uapi2_sysctl_prepare(aiq, 0, 0, RK_AIQ_WORKING_MODE_NORMAL) != XCAM_RETURN_NO_ERROR)
		return -1;
	if (rk_aiq_uapi2_sysctl_start(aiq) != XCAM_RETURN_NO_ERROR)
		return -1;
	if (flip)
		rk_aiq_uapi2_setMirrorFlip(aiq, (flip & 1) != 0, (flip & 2) != 0, 3);
	return 0;
}

/* a fixed sensor frame rate, as sample_comm_isp.c SAMPLE_COMM_ISP_SetFrameRate:
 * fewer frames, less power in the sensor, the ISP and DDR */
static int set_fps(int fps) {
	Uapi_ExpSwAttrV2_t a;
	if (!aiq || rk_aiq_user_api2_ae_getExpSwAttr(aiq, &a) != XCAM_RETURN_NO_ERROR)
		return -1;
	a.stAuto.stFrmRate.isFpsFix = true;
	a.stAuto.stFrmRate.FpsValue = fps;
	return rk_aiq_user_api2_ae_setExpSwAttr(aiq, a) == XCAM_RETURN_NO_ERROR ? 0 : -1;
}

static void isp_deinit(void) {
	if (aiq) {
		if (awake)
			rk_aiq_uapi2_sysctl_stop(aiq, false);
		rk_aiq_uapi2_sysctl_deinit(aiq);
		aiq = NULL;
	}
}

/* ------------------------------------------------------------------ VI */
static int vi_start(void) {
	VI_DEV_ATTR_S dev;
	VI_DEV_BIND_PIPE_S bind;
	VI_CHN_ATTR_S chn;
	memset(&dev, 0, sizeof(dev));
	memset(&bind, 0, sizeof(bind));
	memset(&chn, 0, sizeof(chn));
	/* as luckfox_mpi.cc vi_dev_init() */
	if (RK_MPI_VI_GetDevAttr(0, &dev) == RK_ERR_VI_NOT_CONFIG && RK_MPI_VI_SetDevAttr(0, &dev) != RK_SUCCESS)
		return -1;
	if (RK_MPI_VI_GetDevIsEnable(0) != RK_SUCCESS) {
		if (RK_MPI_VI_EnableDev(0) != RK_SUCCESS)
			return -1;
		bind.u32Num = 1;
		bind.PipeId[0] = VI_PIPE;
		if (RK_MPI_VI_SetDevBindPipe(0, &bind) != RK_SUCCESS)
			return -1;
	}
	chn.stIspOpt.u32BufCount = 2;
	chn.stIspOpt.enMemoryType = VI_V4L2_MEMORY_TYPE_DMABUF;
	chn.stSize.u32Width = width;
	chn.stSize.u32Height = height;
	chn.enPixelFormat = RK_FMT_YUV420SP;
	chn.enCompressMode = COMPRESS_MODE_NONE;
	chn.u32Depth = VI_DEPTH; /* not bound to anything: we fetch frames ourselves */
	return RK_MPI_VI_SetChnAttr(VI_PIPE, VI_CHN, &chn) == RK_SUCCESS ? 0 : -1;
}

/* Awake: ISP running, VI channel streaming at fps.  Asleep: both stopped;
 * with no stream the sensor driver leaves the SC3336 in standby.  The ISP
 * is stopped before the VI stream goes off (sample_comm_isp.h). */
static int wake(int flip, int fps) {
	if (!awake) {
		if (isp_run(flip) || RK_MPI_VI_EnableChn(VI_PIPE, VI_CHN) != RK_SUCCESS)
			return -1;
		awake = 1;
	}
	return fps > 0 ? set_fps(fps) : 0;
}

static void sleep_now(void) {
	if (awake) {
		rk_aiq_uapi2_sysctl_stop(aiq, false);
		RK_MPI_VI_DisableChn(VI_PIPE, VI_CHN);
		awake = 0;
	}
}

/* A frame taken after the command arrived: the channel may hold up to
 * VI_DEPTH frames from before (the head still moving), so drop that many
 * first.  Costs at most two frame times, 67 ms at 30 fps. */
static int fresh_frame(VIDEO_FRAME_INFO_S *f) {
	if (!awake)
		return -1;
	for (int i = 0; i < VI_DEPTH; i++) {
		if (RK_MPI_VI_GetChnFrame(VI_PIPE, VI_CHN, f, 1000) != RK_SUCCESS)
			return -1;
		RK_MPI_VI_ReleaseChnFrame(VI_PIPE, VI_CHN, f);
	}
	return RK_MPI_VI_GetChnFrame(VI_PIPE, VI_CHN, f, 1000) == RK_SUCCESS ? 0 : -1;
}

/* ------------------------------------------------------------------ VENC */
static int venc_create(int chn, RK_CODEC_ID_E type, PIXEL_FORMAT_E fmt, int w, int h, int fps, int qp, int gop) {
	VENC_CHN_ATTR_S a;
	VENC_RECV_PIC_PARAM_S recv;
	memset(&a, 0, sizeof(a));
	a.stVencAttr.enType = type;
	a.stVencAttr.enPixelFormat = fmt;
	a.stVencAttr.u32PicWidth = w;
	a.stVencAttr.u32PicHeight = h;
	a.stVencAttr.u32VirWidth = w;
	a.stVencAttr.u32VirHeight = h;
	a.stVencAttr.u32StreamBufCnt = 2;
	a.stVencAttr.u32BufSize = w * h * 3 / 2;
	a.stVencAttr.enMirror = MIRROR_NONE;
	if (type == RK_VIDEO_ID_JPEG) {
		a.stVencAttr.stAttrJpege.bSupportDCF = RK_FALSE;
		a.stVencAttr.stAttrJpege.stMPFCfg.u8LargeThumbNailNum = 0;
		a.stVencAttr.stAttrJpege.enReceiveMode = VENC_PIC_RECEIVE_SINGLE;
	} else {
		/* Main profile, no B-frames: what layercam/mp4.py expects.
		 * Fixed QP: a timelapse frame changes little from the last
		 * (the print grows by a layer), so a rate target would waste
		 * bits on the static scene or starve the changes. */
		a.stVencAttr.u32Profile = H264E_PROFILE_MAIN;
		a.stRcAttr.enRcMode = VENC_RC_MODE_H264FIXQP;
		a.stRcAttr.stH264FixQp.u32Gop = gop;
		a.stRcAttr.stH264FixQp.u32SrcFrameRateNum = fps;
		a.stRcAttr.stH264FixQp.u32SrcFrameRateDen = 1;
		a.stRcAttr.stH264FixQp.fr32DstFrameRateNum = fps;
		a.stRcAttr.stH264FixQp.fr32DstFrameRateDen = 1;
		a.stRcAttr.stH264FixQp.u32IQp = qp > 2 ? qp - 2 : qp;
		a.stRcAttr.stH264FixQp.u32PQp = qp;
	}
	if (RK_MPI_VENC_CreateChn(chn, &a) != RK_SUCCESS)
		return -1;
	memset(&recv, 0, sizeof(recv));
	recv.s32RecvPicNum = -1; /* we send each frame ourselves */
	return RK_MPI_VENC_StartRecvFrame(chn, &recv) == RK_SUCCESS ? 0 : -1;
}

static void venc_destroy(int chn) {
	RK_MPI_VENC_StopRecvFrame(chn);
	RK_MPI_VENC_DestroyChn(chn);
}

/* encode one frame on chn; -> the stream (release it after use) */
static int encode(int chn, VIDEO_FRAME_INFO_S *f, VENC_STREAM_S *s, VENC_PACK_S *pack) {
	memset(s, 0, sizeof(*s));
	s->pstPack = pack;
	f->stVFrame.u32TimeRef = frame_no++;
	f->stVFrame.u64PTS = now_us();
	if (RK_MPI_VENC_SendFrame(chn, f, 1000) != RK_SUCCESS)
		return -1;
	return RK_MPI_VENC_GetStream(chn, s, 2000) == RK_SUCCESS ? 0 : -1;
}

static int write_all(int fd, const unsigned char *p, size_t n) {
	while (n) {
		ssize_t w = write(fd, p, n);
		if (w < 0) {
			if (errno == EINTR)
				continue;
			return -1;
		}
		p += w;
		n -= (size_t)w;
	}
	return 0;
}

/* an IDR slice (NAL type 5) anywhere in the access unit */
static int has_idr(const unsigned char *p, size_t n) {
	for (size_t i = 0; i + 3 < n; i++)
		if (p[i] == 0 && p[i + 1] == 0 && p[i + 2] == 1 && (p[i + 3] & 0x1f) == 5)
			return 1;
	return 0;
}

/* append one H.264 access unit to the video file; prints the FRAME line */
static void put_frame(int chn, VIDEO_FRAME_INFO_S *f) {
	VENC_STREAM_S s;
	VENC_PACK_S pack;
	if (encode(chn, f, &s, &pack)) {
		reply("ERR encode");
		return;
	}
	const unsigned char *p = (const unsigned char *)RK_MPI_MB_Handle2VirAddr(pack.pMbBlk);
	off_t off = lseek(video_fd, 0, SEEK_END);
	int bad = off < 0 || write_all(video_fd, p, pack.u32Len) || fsync(video_fd);
	int key = has_idr(p, pack.u32Len);
	unsigned len = pack.u32Len;
	RK_MPI_VENC_ReleaseStream(chn, &s);
	if (bad)
		reply("ERR write %s", strerror(errno));
	else
		reply("FRAME %lld %u %d", (long long)off, len, key);
}

/* ------------------------------------------------------------------ commands */
static void cmd_snap(int quality) {
	VIDEO_FRAME_INFO_S f;
	VENC_STREAM_S s;
	VENC_PACK_S pack;
	VENC_JPEG_PARAM_S jp;
	memset(&jp, 0, sizeof(jp));
	jp.u32Qfactor = quality < 1 ? 1 : quality > 99 ? 99 : quality;
	RK_MPI_VENC_SetJpegParam(VENC_JPEG, &jp);
	if (fresh_frame(&f)) {
		reply("ERR no frame from the sensor%s", awake ? "" : " (asleep: WAKE first)");
		return;
	}
	int r = encode(VENC_JPEG, &f, &s, &pack);
	RK_MPI_VI_ReleaseChnFrame(VI_PIPE, VI_CHN, &f);
	if (r) {
		reply("ERR jpeg");
		return;
	}
	printf("JPEG %u\n", pack.u32Len);
	fwrite(RK_MPI_MB_Handle2VirAddr(pack.pMbBlk), 1, pack.u32Len, stdout);
	fflush(stdout);
	RK_MPI_VENC_ReleaseStream(VENC_JPEG, &s);
}

static void cmd_vstart(const char *path, int fps, int qp, int gop) {
	if (video_on) {
		venc_destroy(VENC_H264);
		close(video_fd);
		video_on = 0;
	}
	video_fd = open(path, O_WRONLY | O_CREAT | O_APPEND, 0644);
	if (video_fd < 0) {
		reply("ERR open %s", strerror(errno));
		return;
	}
	/* a new channel starts on an IDR with SPS/PPS, so a stream continued
	 * after a restart is still decodable from that point */
	if (venc_create(VENC_H264, RK_VIDEO_ID_AVC, RK_FMT_YUV420SP, width, height, fps, qp, gop)) {
		close(video_fd);
		reply("ERR h264 encoder");
		return;
	}
	video_on = 1;
	reply("OK");
}

static void cmd_vframe(void) {
	VIDEO_FRAME_INFO_S f;
	if (!video_on) {
		reply("ERR video not started");
		return;
	}
	if (fresh_frame(&f)) {
		reply("ERR no frame from the sensor");
		return;
	}
	put_frame(VENC_H264, &f);
	RK_MPI_VI_ReleaseChnFrame(VI_PIPE, VI_CHN, &f);
}

static void cmd_vstop(void) {
	if (video_on) {
		venc_destroy(VENC_H264);
		close(video_fd);
		video_on = 0;
	}
	reply("OK");
}

static void cmd_night(int on) {
	/* grey picture under IR light: the colours are meaningless without the filter */
	if (aiq && rk_aiq_uapi2_setGrayMode(aiq, on ? RK_AIQ_GRAY_MODE_ON : RK_AIQ_GRAY_MODE_OFF) == XCAM_RETURN_NO_ERROR)
		reply("OK");
	else
		reply("ERR grey mode");
}

static int live(const char *iq_dir, int flip) {
	char line[1024], path[900];
	int a, b, c;
	if (isp_init(iq_dir)) {
		reply("ERR ISP did not start (sensor, IQ file in %s?)", iq_dir);
		return 1;
	}
	if (RK_MPI_SYS_Init() != RK_SUCCESS || vi_start() ||
	    venc_create(VENC_JPEG, RK_VIDEO_ID_JPEG, RK_FMT_YUV420SP, width, height, 30, 0, 0)) {
		reply("ERR media pipeline did not start");
		isp_deinit();
		return 1;
	}
	/* start and stop once: proves the sensor answers, then sleep */
	if (wake(flip, 0)) {
		reply("ERR sensor stream did not start");
		isp_deinit();
		return 1;
	}
	sleep_now();
	reply("READY %d %d", width, height);
	while (fgets(line, sizeof(line), stdin)) {
		if (sscanf(line, "SNAP %d", &a) == 1)
			cmd_snap(a);
		else if (sscanf(line, "VSTART %899s %d %d %d", path, &a, &b, &c) == 4)
			cmd_vstart(path, a, b, c);
		else if (!strncmp(line, "VFRAME", 6))
			cmd_vframe();
		else if (!strncmp(line, "VSTOP", 5))
			cmd_vstop();
		else if (sscanf(line, "NIGHT %d", &a) == 1)
			cmd_night(a);
		else if (sscanf(line, "WAKE %d", &a) == 1)
			wake(flip, a) ? reply("ERR wake") : reply("OK");
		else if (sscanf(line, "FPS %d", &a) == 1)
			awake && !set_fps(a) ? reply("OK") : reply("ERR fps");
		else if (!strncmp(line, "SLEEP", 5)) {
			sleep_now();
			reply("OK");
		}
		else if (!strncmp(line, "PING", 4))
			reply("OK %d %d", width, height);
		else if (!strncmp(line, "QUIT", 4))
			break;
		else
			reply("ERR unknown command");
	}
	/* stdin closed (the service stopped) or QUIT: let go of the camera */
	if (video_on)
		cmd_vstop();
	venc_destroy(VENC_JPEG);
	isp_deinit();
	if (awake)
		RK_MPI_VI_DisableChn(VI_PIPE, VI_CHN);
	awake = 0;
	RK_MPI_VI_DisableDev(0);
	RK_MPI_SYS_Exit();
	return 0;
}

/* ------------------------------------------------------------------ offline */
#ifdef HAVE_LIBJPEG
/* decode into an RGB888 buffer of w x h; 0 on success */
static int decode_jpeg(const char *path, unsigned char *dst, int w, int h, int *got_w, int *got_h) {
	struct jpeg_decompress_struct d;
	struct jpeg_error_mgr e;
	FILE *fp = fopen(path, "rb");
	if (!fp)
		return -1;
	d.err = jpeg_std_error(&e);
	jpeg_create_decompress(&d);
	jpeg_stdio_src(&d, fp);
	jpeg_read_header(&d, TRUE);
	d.out_color_space = JCS_RGB;
	jpeg_start_decompress(&d);
	*got_w = d.output_width;
	*got_h = d.output_height;
	int ok = dst && (int)d.output_width == w && (int)d.output_height == h;
	while (d.output_scanline < d.output_height) {
		JSAMPROW row = dst ? dst + (size_t)d.output_scanline * w * 3 : NULL;
		unsigned char scratch[16384 * 3];
		if (!ok)
			row = scratch;
		if ((int)d.output_width > 16384)
			break;
		jpeg_read_scanlines(&d, &row, 1);
	}
	jpeg_finish_decompress(&d);
	jpeg_destroy_decompress(&d);
	fclose(fp);
	return ok ? 0 : -1;
}

static int encode_jpegs(const char *list, const char *out, int fps, int qp) {
	char path[1024];
	int w = 0, h = 0, gw, gh;
	FILE *l = fopen(list, "r");
	if (!l) {
		reply("ERR cannot read %s", list);
		return 1;
	}
	/* the first frame sets the size */
	if (!fgets(path, sizeof(path), l)) {
		reply("ERR empty list");
		return 1;
	}
	path[strcspn(path, "\r\n")] = 0;
	decode_jpeg(path, NULL, 0, 0, &w, &h);
	if (w <= 0 || h <= 0 || (w & 1) || (h & 1)) {
		reply("ERR first frame unreadable or odd-sized");
		return 1;
	}
	rewind(l);
	if (RK_MPI_SYS_Init() != RK_SUCCESS || venc_create(VENC_H264, RK_VIDEO_ID_AVC, RK_FMT_RGB888, w, h, fps, qp, 30)) {
		reply("ERR h264 encoder");
		return 1;
	}
	MB_POOL_CONFIG_S pc;
	memset(&pc, 0, sizeof(pc));
	pc.u64MBSize = (RK_U64)w * h * 3;
	pc.u32MBCnt = 1;
	pc.enAllocType = MB_ALLOC_TYPE_DMA;
	MB_POOL pool = RK_MPI_MB_CreatePool(&pc);
	MB_BLK blk = RK_MPI_MB_GetMB(pool, pc.u64MBSize, RK_TRUE);
	unsigned char *rgb = (unsigned char *)RK_MPI_MB_Handle2VirAddr(blk);
	video_fd = open(out, O_WRONLY | O_CREAT | O_APPEND, 0644);
	if (video_fd < 0 || !rgb) {
		reply("ERR setup");
		return 1;
	}
	/* frame layout as luckfox_pico_rtsp_opencv_capture's main.cc */
	VIDEO_FRAME_INFO_S f;
	memset(&f, 0, sizeof(f));
	f.stVFrame.u32Width = w;
	f.stVFrame.u32Height = h;
	f.stVFrame.u32VirWidth = w;
	f.stVFrame.u32VirHeight = h;
	f.stVFrame.enPixelFormat = RK_FMT_RGB888;
	f.stVFrame.u32FrameFlag = 160;
	f.stVFrame.pMbBlk = blk;
	while (fgets(path, sizeof(path), l)) {
		path[strcspn(path, "\r\n")] = 0;
		if (!path[0])
			continue;
		if (decode_jpeg(path, rgb, w, h, &gw, &gh)) {
			fprintf(stderr, "skipping %s (%dx%d)\n", path, gw, gh);
			continue;
		}
		RK_MPI_SYS_MmzFlushCache(blk, RK_FALSE); /* CPU writes -> encoder reads */
		put_frame(VENC_H264, &f);
	}
	fclose(l);
	close(video_fd);
	venc_destroy(VENC_H264);
	RK_MPI_MB_ReleaseMB(blk);
	RK_MPI_MB_DestroyPool(pool);
	RK_MPI_SYS_Exit();
	reply("DONE");
	return 0;
}
#endif

int main(int argc, char **argv) {
	const char *iq = "/etc/iqfiles", *list = NULL, *out = NULL;
	int flip = 0, fps = 30, qp = 28;
	signal(SIGPIPE, SIG_IGN);
	for (int i = 1; i < argc; i++) {
		if (!strcmp(argv[i], "--iq") && i + 1 < argc)
			iq = argv[++i];
		else if (!strcmp(argv[i], "--flip") && i + 1 < argc)
			flip = atoi(argv[++i]);
		else if (!strcmp(argv[i], "--width") && i + 1 < argc)
			width = atoi(argv[++i]);
		else if (!strcmp(argv[i], "--height") && i + 1 < argc)
			height = atoi(argv[++i]);
		else if (!strcmp(argv[i], "--fps") && i + 1 < argc)
			fps = atoi(argv[++i]);
		else if (!strcmp(argv[i], "--qp") && i + 1 < argc)
			qp = atoi(argv[++i]);
		else if (!strcmp(argv[i], "--encode-jpegs") && i + 2 < argc) {
			list = argv[++i];
			out = argv[++i];
		} else {
			fprintf(stderr, "usage: %s [--iq DIR] [--flip 0-3] | --encode-jpegs LIST OUT.h264 [--fps N] [--qp N]\n",
			        argv[0]);
			return 2;
		}
	}
	if (list) {
#ifdef HAVE_LIBJPEG
		return encode_jpegs(list, out, fps, qp);
#else
		(void)out, (void)fps, (void)qp;
		reply("ERR built without libjpeg");
		return 1;
#endif
	}
	return live(iq, flip);
}
