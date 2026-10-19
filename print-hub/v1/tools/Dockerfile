# The build toolchain for Print Hub v1, pinned: KiCad 10.0.6 (pcbnew Python
# module and kicad-cli), Freerouting 2.5.0 (and 1.9.0 as a fallback),
# ngspice, build123d for the enclosure, and the Python packages src/ uses.
#
# KiCad 10.0.7 is the newest stable release (7 Oct 2026), but Docker Hub has
# no kicad/kicad:10.0.7 image yet (checked 17 Oct 2026): 10.0.6 is the newest
# one that can be pinned by digest.
#
# Build from the repository root:
#
#   curl -fsSL -o out/freerouting-2.5.0-linux-x64.zip \
#     https://github.com/freerouting/freerouting/releases/download/v2.5.0/freerouting-2.5.0-linux-x64.zip
#   curl -fsSL -o out/freerouting-1.9.0.jar \
#     https://github.com/freerouting/freerouting/releases/download/v1.9.0/freerouting-1.9.0.jar
#   docker build -t ogkicad-printhub:1 -f print-hub/v1/tools/Dockerfile out
#
# then run make.py inside it (print-hub/v1/tools/kd does this).
FROM kicad/kicad:10.0.6@sha256:18693567392b80da435f9fa952ce3a3e534c66eb5a6033f5b9c80aa3b19dd3ec
USER root
RUN apt-get update -qq \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
      python3-pip openjdk-21-jre xvfb xauth ngspice > /dev/null \
 && rm -rf /var/lib/apt/lists/*
RUN pip3 install --break-system-packages -q numpy==2.5.4 shapely==2.2.0 Pillow==13.0.0 matplotlib==3.11.2 \
      pypdf==6.21.1 uharfbuzz==0.56.3 fonttools==4.67.0 pymupdf==1.28.2 scipy==1.18.1 \
 && pip3 install --break-system-packages -q --no-deps gerbonara==1.6.3 \
 && pip3 install --break-system-packages -q --ignore-installed typing_extensions build123d==0.13.0
# 3D models of the standard R/C chips, for the renders and the STEP: only
# these files out of Debian's kicad-packages3d (apt checks the package
# against its signed index)
RUN cd /tmp && apt-get update -qq && apt-get download -qq kicad-packages3d \
 && dpkg-deb --fsys-tarfile kicad-packages3d_*.deb | tar -x -C / \
      ./usr/share/kicad/3dmodels/Resistor_SMD.3dshapes/R_0402_1005Metric.step \
      ./usr/share/kicad/3dmodels/Resistor_SMD.3dshapes/R_0603_1608Metric.step \
      ./usr/share/kicad/3dmodels/Resistor_SMD.3dshapes/R_1206_3216Metric.step \
      ./usr/share/kicad/3dmodels/Capacitor_SMD.3dshapes/C_0402_1005Metric.step \
      ./usr/share/kicad/3dmodels/Capacitor_SMD.3dshapes/C_0603_1608Metric.step \
      ./usr/share/kicad/3dmodels/Capacitor_SMD.3dshapes/C_0805_2012Metric.step \
      ./usr/share/kicad/3dmodels/Capacitor_SMD.3dshapes/C_1206_3216Metric.step \
 && rm kicad-packages3d_*.deb && rm -rf /var/lib/apt/lists/*
ENV KICAD10_3DMODEL_DIR=/usr/share/kicad/3dmodels
# Freerouting 2.5.0, the current release (5 Oct 2026), as its official Linux
# bundle with its own Java runtime; sha256 as GitHub publishes it
COPY freerouting-2.5.0-linux-x64.zip /opt/
RUN echo "e8ffca14914e5307a2fa9aea723fb93d11b99bebda20d126472da5460c03196e  /opt/freerouting-2.5.0-linux-x64.zip" | sha256sum -c - \
 && cd /opt && python3 -m zipfile -e freerouting-2.5.0-linux-x64.zip . && rm freerouting-2.5.0-linux-x64.zip \
 && chmod -R a+rx /opt/freerouting-2.5.0-linux-x64
COPY freerouting-1.9.0.jar /opt/freerouting-1.9.0.jar
RUN echo "9084a4888937a7f31f857ecc12aa7a37407f51160e4d2892dff9c9bb47ae3102  /opt/freerouting-1.9.0.jar" | sha256sum -c -
ENV FREEROUTING_JAR=/opt/freerouting-1.9.0.jar FREEROUTING2=/opt/freerouting-2.5.0-linux-x64/bin/freerouting PYTHONHASHSEED=0
