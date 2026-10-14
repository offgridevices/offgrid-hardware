# The build toolchain for Ridge 3 (ridge-3/), pinned: KiCad 10.0.6 (the
# pcbnew Python module and kicad-cli), the Python packages src/ and sim/ use,
# ngspice, poppler's pdftotext (verify.py's datasheets), Freerouting 1.9.0
# for make.py --reroute, and the 3D models from KiCad's own library that the
# boards use, for the renders and the STEP.  CI (.github/workflows/ci.yml,
# job ridge-3) runs make.py --fab-only in the same KiCad image with the same
# Python packages, less matplotlib and pyamg.
#
# Build it from the repository root (the build context is ridge-3/, for
# requirements.txt; Freerouting and the 3D models are downloaded and checked
# against their sha256):
#
#   docker build -t ridge3-build -f ridge-3/tools/Dockerfile ridge-3
#
# then run make.py, verify.py or a simulation in it, the checkout mounted at /w:
#
#   docker run --rm -u "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD":/w -w /w/ridge-3 \
#     ridge3-build python3 src/make.py
#
# The image is Debian 13 with Python 3.13, not the Ubuntu 24.04 and Python
# 3.12 that built the committed outputs (requirements.txt).  numpy, SciPy,
# Pillow, matplotlib and pyamg have no wheels for 3.13 at the versions
# there, so the first four are Debian 13's versions here and pyamg is 5.2.1,
# the first with one; all come from pip, so that they do not move with
# Debian's updates, and the fab files do not depend on them.  Shapely does
# matter: KiKit builds the panels' outline with it, and with Debian's
# Shapely 2.1 the panel Gerbers come out different from the committed ones.
# 2.0.7, as pinned here, gives them byte for byte.  The renders and the STEP
# are made again only when their inputs change (src/stable.py).  The
# heatsink's CAD files need CadQuery besides (requirements-cadquery.txt).

# The official KiCad 10.0.6 image, pinned by digest (Docker Hub, kicad/kicad:10.0.6)
FROM kicad/kicad:10.0.6@sha256:18693567392b80da435f9fa952ce3a3e534c66eb5a6033f5b9c80aa3b19dd3ec
USER root
RUN apt-get update -qq \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
      ca-certificates curl python3-pip openjdk-21-jre xvfb xauth ngspice poppler-utils > /dev/null \
 && rm -rf /var/lib/apt/lists/*
# The Python packages, each at a fixed version: requirements.txt's pins as a
# constraint (-c) for what it lists, the rest here (requirements.txt's
# comments say why these versions); gerbonara without its requirements (a
# web server it does not need here)
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --break-system-packages -q -c /tmp/requirements.txt \
      numpy==2.2.4 scipy==1.15.3 shapely==2.0.7 pillow==11.1.0 fonttools==4.46.0 \
      pypdf uharfbuzz pymupdf scikit-image kikit \
      matplotlib==3.10.1 contourpy==1.4.0 cycler==0.12.1 kiwisolver==1.5.1 pyparsing==3.3.3 \
      python-dateutil==2.9.0.post0 six==1.17.0 \
 && pip3 install --break-system-packages -q --no-deps gerbonara==1.6.3 \
 && pip3 install --break-system-packages -q pyamg==5.2.1 \
 && rm /tmp/requirements.txt
# KiCad's own 3D models that the boards name (${KICAD10_3DMODEL_DIR}; the
# rest are in ridge-3/aio.3dshapes): kicad-packages3D at its 10.0.6 tag, the
# same bytes as Ubuntu's kicad-packages3d 10.0.6~ubuntu24.04.1, so the
# renders' and the STEP's inputs keys match the committed ones.
RUN mkdir -p /usr/share/kicad/3dmodels && cd /usr/share/kicad/3dmodels \
 && printf '%s\n' \
    "240fbd4fecce88248dd9f9898624c5e433deb8f661a3f13a0e66d2c8adbaba39  Button_Switch_SMD.3dshapes/SW_Push_1P1T-SH_NO_CK_KMR2xxG.step" \
    "03e44c4b2b727b8d4b6b1fd598cbd12dd5e614f1dfeefa96a92a07e3a3b312a2  Capacitor_SMD.3dshapes/C_0402_1005Metric.step" \
    "4857b3dc717675bf1fb22edda622ac3b3ae03cf44d81eefaf3fa3ba3a86d84c1  Capacitor_SMD.3dshapes/C_0603_1608Metric.step" \
    "9a669c1a2f1ea25b88b401acef6efeaa80a067bd7da9db6993de719a7fbe155c  Capacitor_SMD.3dshapes/C_0805_2012Metric.step" \
    "f8510481c5044113cf49b0fa6dd54ddab9224508bd6808e1afab8ef0cefdefc9  Capacitor_SMD.3dshapes/C_1210_3225Metric.step" \
    "6338ce740fa231c2d3dcc6384e0576994a47240a312a21413cb85d76990a69a0  Connector_USB.3dshapes/USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal.step" \
    "303a886d7d6d526df33deb11f533d5e25b0f1acdadadb70657d7df635d21352e  Inductor_SMD.3dshapes/L_0201_0603Metric.step" \
    "8bf2ae2bbd9d8b716db21d8d7fb903fac5ba2696150c3ec2e35bcea17b208ff2  Inductor_SMD.3dshapes/L_0402_1005Metric.step" \
    "33893da67f0e1d523ba6096fc78c9fb67e7770efb072fcf51f480f9365706a1d  Resistor_SMD.3dshapes/R_0201_0603Metric.step" \
    "91507e5af4251cb4ef38e04889c9b98da29904432bd83786bba13ae9b605eacb  Resistor_SMD.3dshapes/R_0402_1005Metric.step" \
    "1875571c326d0d9e96f36b4efeb8094068ef7619f0a449c781caf0b49c2e5861  Resistor_SMD.3dshapes/R_0603_1608Metric.step" \
    > /tmp/3dmodels.sha256 \
 && cut -c67- /tmp/3dmodels.sha256 | while read -r f; do \
      mkdir -p "$(dirname "$f")" \
      && curl -fsSL -o "$f" "https://gitlab.com/kicad/libraries/kicad-packages3D/-/raw/10.0.6/$f" || exit 1; \
    done \
 && sha256sum -c --quiet /tmp/3dmodels.sha256 \
 && rm /tmp/3dmodels.sha256
ENV KICAD10_3DMODEL_DIR=/usr/share/kicad/3dmodels
# Freerouting 1.9.0, for make.py --reroute (the GitHub release's jar)
RUN curl -fsSL -o /opt/freerouting-1.9.0.jar \
      https://github.com/freerouting/freerouting/releases/download/v1.9.0/freerouting-1.9.0.jar \
 && echo "9084a4888937a7f31f857ecc12aa7a37407f51160e4d2892dff9c9bb47ae3102  /opt/freerouting-1.9.0.jar" \
    | sha256sum -c -
ENV FREEROUTING_JAR=/opt/freerouting-1.9.0.jar PYTHONHASHSEED=0
