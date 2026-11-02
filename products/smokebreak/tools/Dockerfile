# The build toolchain for this board, pinned: KiCad 10.0.7 (pcbnew Python
# module and kicad-cli), Freerouting 2.5.0, ngspice and the Python packages
# src/, sim/ and firmware/ use.  Build from the repository root:
#
#   mkdir -p out && curl -fsSL -o out/freerouting-2.5.0.jar \
#     https://github.com/freerouting/freerouting/releases/download/v2.5.0/freerouting-2.5.0.jar
#   curl -fsSL -o out/temurin-25-jre.tar.gz \
#     https://github.com/adoptium/temurin25-binaries/releases/download/jdk-25.0.4.1%2B1/OpenJDK25U-jre_x64_linux_hotspot_25.0.4.1_1.tar.gz
#   docker build -t sbkicad:10 -f smokebreak/v1/tools/Dockerfile out
#
# then run commands inside it with smokebreak/v1/tools/kd.  The case
# (enclosure/) is built with CadQuery 2.8 in its own Python environment:
# `pip install cadquery==2.8.0 trimesh` (it is a large install, kept out of
# this image).
# The official KiCad 10.0.7 image, pinned by digest (Docker Hub, kicad/kicad:10.0.7)
FROM kicad/kicad:10.0.7@sha256:3224d1bf143185ecc1bd3a1082a36f37f0f4e59d707983a16515a845e3737fc6
USER root
RUN apt-get update -qq \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
      python3-pip ngspice > /dev/null \
 && rm -rf /var/lib/apt/lists/*
RUN pip3 install --break-system-packages -q numpy shapely Pillow matplotlib uharfbuzz fonttools pytest
# 3D models of the standard R/C chips, for the renders: only these files out
# of Debian's kicad-packages3d (apt checks the package against its signed index)
RUN cd /tmp && apt-get update -qq && apt-get download -qq kicad-packages3d \
 && dpkg-deb --fsys-tarfile kicad-packages3d_*.deb | tar -x -C / --wildcards \
      './usr/share/kicad/3dmodels/Resistor_SMD.3dshapes/R_0*_*Metric.step' \
      './usr/share/kicad/3dmodels/Resistor_SMD.3dshapes/R_1206_3216Metric.step' \
      './usr/share/kicad/3dmodels/Capacitor_SMD.3dshapes/C_0*_*Metric.step' \
      './usr/share/kicad/3dmodels/Capacitor_SMD.3dshapes/C_1210_3225Metric.step' \
 && rm kicad-packages3d_*.deb && rm -rf /var/lib/apt/lists/*
ENV KICAD10_3DMODEL_DIR=/usr/share/kicad/3dmodels
# Freerouting 2.5.0 needs Java 25: Eclipse Temurin's JRE (Adoptium publishes its sha256)
COPY temurin-25-jre.tar.gz /opt/
RUN echo "1731a34baadec5479258ea0202e4d5d865d2efeee60cb0c7d7eb056fe96ca219  /opt/temurin-25-jre.tar.gz" | sha256sum -c - \
 && mkdir -p /opt/java25 && tar -xzf /opt/temurin-25-jre.tar.gz -C /opt/java25 --strip-components=1 \
 && rm /opt/temurin-25-jre.tar.gz
COPY freerouting-2.5.0.jar /opt/freerouting-2.5.0.jar
RUN echo "f6f51bb02245e8e717f9359bd260cc9c5c0b1bc0acc8b7cb2cd5b8ffeb5de3c7  /opt/freerouting-2.5.0.jar" | sha256sum -c -
ENV FREEROUTING_JAR=/opt/freerouting-2.5.0.jar FREEROUTING_JAVA=/opt/java25/bin/java PYTHONHASHSEED=0
