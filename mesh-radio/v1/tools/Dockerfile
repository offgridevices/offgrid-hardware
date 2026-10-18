# The build toolchain for this board, pinned: KiCad 10.0.7 (pcbnew Python
# module and kicad-cli), Freerouting 1.9.0, KiKit, ngspice and the Python
# packages src/ uses.  Build from the repository root:
#
#   curl -fsSL -o out/freerouting-1.9.0.jar \
#     https://github.com/freerouting/freerouting/releases/download/v1.9.0/freerouting-1.9.0.jar
#   curl -fsSL -o out/freerouting-2.4.1-linux-x64.zip \
#     https://github.com/freerouting/freerouting/releases/download/v2.4.1/freerouting-2.4.1-linux-x64.zip
#   docker build -t ogkicad:10 -f mesh-radio/v1/tools/Dockerfile out
#
# then run make.py inside it (mesh-radio/v1/tools/kd does this).
# The official KiCad 10.0.7 image, pinned by digest (Docker Hub, kicad/kicad:10.0.7)
FROM kicad/kicad:10.0.7@sha256:3224d1bf143185ecc1bd3a1082a36f37f0f4e59d707983a16515a845e3737fc6
USER root
RUN apt-get update -qq \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
      python3-pip openjdk-21-jre xvfb xauth ngspice > /dev/null \
 && rm -rf /var/lib/apt/lists/*
RUN pip3 install --break-system-packages -q numpy shapely Pillow matplotlib pypdf \
      uharfbuzz fonttools pymupdf scipy scikit-image kikit \
 && pip3 install --break-system-packages -q --no-deps gerbonara
# 3D models of the standard R/C chips, for the renders: only these files
# out of Debian's kicad-packages3d (apt checks the package against its
# signed index)
RUN cd /tmp && apt-get update -qq && apt-get download -qq kicad-packages3d \
 && dpkg-deb --fsys-tarfile kicad-packages3d_*.deb | tar -x -C / \
      ./usr/share/kicad/3dmodels/Resistor_SMD.3dshapes/R_0201_0603Metric.step \
      ./usr/share/kicad/3dmodels/Resistor_SMD.3dshapes/R_0402_1005Metric.step \
      ./usr/share/kicad/3dmodels/Capacitor_SMD.3dshapes/C_0201_0603Metric.step \
      ./usr/share/kicad/3dmodels/Capacitor_SMD.3dshapes/C_0402_1005Metric.step \
      ./usr/share/kicad/3dmodels/Capacitor_SMD.3dshapes/C_0603_1608Metric.step \
      ./usr/share/kicad/3dmodels/Capacitor_SMD.3dshapes/C_0805_2012Metric.step \
 && rm kicad-packages3d_*.deb && rm -rf /var/lib/apt/lists/*
ENV KICAD10_3DMODEL_DIR=/usr/share/kicad/3dmodels
COPY freerouting-1.9.0.jar /opt/freerouting-1.9.0.jar
# sha256 9084a4888937a7f31f857ecc12aa7a37407f51160e4d2892dff9c9bb47ae3102
RUN echo "9084a4888937a7f31f857ecc12aa7a37407f51160e4d2892dff9c9bb47ae3102  /opt/freerouting-1.9.0.jar" | sha256sum -c -
# Freerouting 2.4.1, the current release, as its official Linux bundle
# (it carries the Java 25 runtime it needs; GitHub publishes its sha256)
COPY freerouting-2.4.1-linux-x64.zip /opt/
RUN echo "3ad5a956ab474b12f331d24195feadac90e8344b8e013c6a4ab26e203ce51519  /opt/freerouting-2.4.1-linux-x64.zip" | sha256sum -c - \
 && cd /opt && python3 -m zipfile -e freerouting-2.4.1-linux-x64.zip . && rm freerouting-2.4.1-linux-x64.zip \
 && chmod -R a+rx /opt/freerouting-2.4.1-linux-x64
ENV FREEROUTING_JAR=/opt/freerouting-1.9.0.jar FREEROUTING2=/opt/freerouting-2.4.1-linux-x64/bin/freerouting PYTHONHASHSEED=0
