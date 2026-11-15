FROM apache/spark:4.0.1-scala2.13-java17-python3-ubuntu

ARG HADOOP_AWS_VERSION=3.4.1
ARG AWS_SDK_V2_VERSION=2.24.6

USER root

# S3A 커넥터: Spark 4.0.1 에 번들된 hadoop-client 3.4.1 과 버전을 반드시 맞춘다.
ADD --chmod=644 https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/${HADOOP_AWS_VERSION}/hadoop-aws-${HADOOP_AWS_VERSION}.jar /opt/spark/jars/
ADD --chmod=644 https://repo1.maven.org/maven2/software/amazon/awssdk/bundle/${AWS_SDK_V2_VERSION}/bundle-${AWS_SDK_V2_VERSION}.jar /opt/spark/jars/

COPY requirements.txt /tmp/requirements.txt
# jammy 기본 pip 22.0.2 는 pyproject([project]) 메타데이터를 못 읽어 UNKNOWN 으로 설치하므로 먼저 업그레이드
RUN pip3 install --no-cache-dir --upgrade "pip==24.3.1" "setuptools==75.6.0" \
 && pip3 install --no-cache-dir -r /tmp/requirements.txt

# 커스텀 DataSource 패키지를 site-packages 에 설치 → driver/executor 모두 import 가능
COPY pyproject.toml /opt/build/public-api-source/
COPY public_api_source /opt/build/public-api-source/public_api_source
RUN pip3 install --no-cache-dir /opt/build/public-api-source && rm -rf /opt/build

COPY jobs /opt/spark/work-dir/jobs

USER spark
