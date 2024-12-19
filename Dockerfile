FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update -y
RUN apt-get install -y git openjdk-11-jdk htop
RUN apt-get install -y cpanminus perl build-essential make curl unzip subversion
RUN apt-get install -y python3.9 python3-pip
RUN apt-get clean

ENV JAVA_HOME /usr/lib/jvm/java-11-openjdk-amd64/

WORKDIR /

RUN git clone https://github.com/rjust/defects4j.git defects4j

RUN cpanm Module::Pluggable -f

RUN cpanm --installdeps /defects4j
RUN /defects4j/init.sh

ENV PATH="/defects4j/framework/bin:${PATH}"

RUN pip install tqdm

ADD ./ /LLM-Code-Repair

ENTRYPOINT ["/bin/bash"]