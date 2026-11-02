# The build toolchain for LayerCam v1, pinned: KiCad 10.0.7 (pcbnew Python
# module and kicad-cli; the newest stable release, image published 18 Oct
# 2026), Freerouting 1.9.0 and 2.5.0 (2.5.0, with its fan-out pass, for the
# main board's 0.35 mm-pitch SoC; it needs Java 25), ngspice, and the
# Python packages src/ uses.
#
# Build from the repository root:
#
#   curl -fsSL -o out/freerouting-1.9.0.jar \
#     https://github.com/freerouting/freerouting/releases/download/v1.9.0/freerouting-1.9.0.jar
#   curl -fsSL -o out/freerouting-2.5.0.jar \
#     https://github.com/freerouting/freerouting/releases/download/v2.5.0/freerouting-2.5.0.jar
#   curl -fsSL -o out/temurin-25-jre.tar.gz \
#     https://github.com/adoptium/temurin25-binaries/releases/download/jdk-25.0.4.1%2B1/OpenJDK25U-jre_x64_linux_hotspot_25.0.4.1_1.tar.gz
#   docker build -t ogkicad-layercam:2 -f layercam/v1/tools/Dockerfile out
#
# then run make.py inside it (layercam/v1/tools/kd does this).
FROM kicad/kicad:10.0.7@sha256:3224d1bf143185ecc1bd3a1082a36f37f0f4e59d707983a16515a845e3737fc6
USER root
RUN apt-get update -qq \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
      python3-pip openjdk-21-jre xvfb xauth ngspice > /dev/null \
 && rm -rf /var/lib/apt/lists/*
RUN pip3 install --break-system-packages -q numpy==2.5.4 shapely==2.2.0 Pillow==13.0.0 matplotlib==3.11.2 \
      pypdf==6.21.1 uharfbuzz==0.56.3 fonttools==4.67.0 pymupdf==1.28.2 scipy==1.18.1 trimesh==5.2.0 \
 && pip3 install --break-system-packages -q --no-deps gerbonara==1.6.3
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
      ./usr/share/kicad/3dmodels/Inductor_SMD.3dshapes/L_0402_1005Metric.step \
 && rm kicad-packages3d_*.deb && rm -rf /var/lib/apt/lists/*
ENV KICAD10_3DMODEL_DIR=/usr/share/kicad/3dmodels
COPY freerouting-1.9.0.jar /opt/freerouting-1.9.0.jar
RUN echo "9084a4888937a7f31f857ecc12aa7a37407f51160e4d2892dff9c9bb47ae3102  /opt/freerouting-1.9.0.jar" | sha256sum -c -
ENV FREEROUTING_JAR=/opt/freerouting-1.9.0.jar PYTHONHASHSEED=0
# Freerouting 2.5.0 needs Java 25: Eclipse Temurin's JRE (Adoptium publishes its sha256)
COPY temurin-25-jre.tar.gz /opt/
RUN echo "1731a34baadec5479258ea0202e4d5d865d2efeee60cb0c7d7eb056fe96ca219  /opt/temurin-25-jre.tar.gz" | sha256sum -c - \
 && mkdir -p /opt/java25 && tar -xzf /opt/temurin-25-jre.tar.gz -C /opt/java25 --strip-components=1 \
 && rm /opt/temurin-25-jre.tar.gz
COPY freerouting-2.5.0.jar /opt/freerouting-2.5.0.jar
RUN echo "f6f51bb02245e8e717f9359bd260cc9c5c0b1bc0acc8b7cb2cd5b8ffeb5de3c7  /opt/freerouting-2.5.0.jar" | sha256sum -c -
ENV FREEROUTING2="/opt/java25/bin/java -jar /opt/freerouting-2.5.0.jar"
