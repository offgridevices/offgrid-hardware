/* The maze router's search (finish._route_in) in C: A* over the routing
 * layers' grids, eight directions per layer plus a through via to any other
 * layer, with a bend cost and soft (rippable) copper at a price.
 * Same costs and the same first-pop rule as the Python version it replaces.
 * Node index: (layer * H + j) * W + i.  Returns the path length (nodes,
 * source first, written to path_out as node indices), 0 if there is no
 * path within max_expand, -1 if path_out is too short or memory runs out. */
#include <stdlib.h>
#include <stdint.h>
#include <math.h>
#include <string.h>

typedef struct { float f; int32_t n; } ent;

static int push(ent **h, long *len, long *cap, float f, int32_t n)
{
    if (*len == *cap) {
        long nc = *cap ? *cap * 2 : 1 << 16;
        ent *p = realloc(*h, nc * sizeof(ent));
        if (!p) return -1;
        *h = p; *cap = nc;
    }
    long i = (*len)++;
    while (i > 0) {
        long q = (i - 1) / 2;
        if ((*h)[q].f <= f) break;
        (*h)[i] = (*h)[q]; i = q;
    }
    (*h)[i].f = f; (*h)[i].n = n;
    return 0;
}

static ent pop(ent *h, long *len)
{
    ent top = h[0], last = h[--(*len)];
    long i = 0, n = *len;
    for (;;) {
        long a = 2 * i + 1, b = a + 1, m = i;
        float fm = last.f;
        if (a < n && h[a].f < fm) { m = a; fm = h[a].f; }
        if (b < n && h[b].f < fm) { m = b; }
        if (m == i) break;
        h[i] = h[m]; i = m;
    }
    if (n) h[i] = last;
    return top;
}

long astar(int L, int H, int W,
           const uint8_t *block, const uint8_t *sblock, const float *sweight,
           const uint8_t *vblock, const uint8_t *vsoft, const float *vweight,
           const uint8_t *src, const uint8_t *dst,
           float rip_cost, float vcost, float bend, float tci, float tcj,
           long max_expand, int32_t *path_out, long path_cap)
{
    static const int di[8] = {1, -1, 0, 0, 1, 1, -1, -1};
    static const int dj[8] = {0, 0, 1, -1, 1, -1, 1, -1};
    long N = (long)L * H * W, HW = (long)H * W;
    float *cost = malloc(N * sizeof(float));
    int32_t *par = malloc(N * sizeof(int32_t));
    uint8_t *pdir = malloc(N);
    uint8_t *closed = calloc(N, 1);
    ent *heap = NULL; long hl = 0, hc = 0;
    long result = 0;
    if (!cost || !par || !pdir || !closed) { result = -1; goto done; }
    for (long k = 0; k < N; k++) cost[k] = INFINITY;
    for (long k = 0; k < N; k++) {
        if (src[k]) {
            cost[k] = 0; par[k] = -1; pdir[k] = 9;       /* 9: no direction yet */
            if (push(&heap, &hl, &hc, 0, (int32_t)k)) { result = -1; goto done; }
        }
    }
    long n = 0, found = -1;
    while (hl && n < max_expand) {
        ent e = pop(heap, &hl);
        long k = e.n;
        if (closed[k]) continue;
        closed[k] = 1;
        n++;
        if (dst[k]) { found = k; break; }
        int li = k / HW; long r = k % HW; int j = r / W, i = r % W;
        float c = cost[k];
        const uint8_t *blk = block + li * HW, *sb = sblock + li * HW;
        const float *sw = sweight + li * HW;
        for (int d = 0; d < 8; d++) {
            int ni = i + di[d], nj = j + dj[d];
            if (ni < 0 || ni >= W || nj < 0 || nj >= H) continue;
            long cell = (long)nj * W + ni, nk = li * HW + cell;
            if (closed[nk]) continue;
            int free_end = src[nk] || dst[nk];
            if (blk[cell] && !free_end) continue;
            float step = (d >= 4) ? 1.414f : 1.0f;
            float nc = c + step + ((pdir[k] != 9 && pdir[k] != d) ? bend : 0);
            if (sb[cell] && !free_end) {
                float wgt = sw[cell];
                nc += sb[(long)j * W + i] ? step * 2 * wgt : rip_cost * wgt;
            }
            if (nc < cost[nk]) {
                cost[nk] = nc; par[nk] = (int32_t)k; pdir[nk] = (uint8_t)d;
                float h = hypotf(ni - tci, nj - tcj) * 0.9f;
                if (push(&heap, &hl, &hc, nc + h, (int32_t)nk)) { result = -1; goto done; }
            }
        }
        if (!vblock[r]) {
            for (int lj = 0; lj < L; lj++) {
                if (lj == li) continue;
                long nk = lj * HW + r;
                if (block[nk] && !src[nk] && !dst[nk]) continue;
                if (closed[nk]) continue;
                float nc = c + vcost + (vsoft[r] ? rip_cost * vweight[r] : 0);
                if (nc < cost[nk]) {
                    cost[nk] = nc; par[nk] = (int32_t)k; pdir[nk] = 8;   /* 8: via */
                    float h = hypotf(i - tci, j - tcj) * 0.9f;
                    if (push(&heap, &hl, &hc, nc + h, (int32_t)nk)) { result = -1; goto done; }
                }
            }
        }
    }
    if (found >= 0) {
        long len = 0;
        for (long k = found; k >= 0; k = par[k]) len++;
        if (len > path_cap) { result = -1; goto done; }
        long q = len;
        for (long k = found; k >= 0; k = par[k]) path_out[--q] = (int32_t)k;
        result = len;
    }
done:
    free(cost); free(par); free(pdir); free(closed); free(heap);
    return result;
}
