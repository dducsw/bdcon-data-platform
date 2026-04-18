#!/bin/sh
set -e

download_and_verify() {
    artifact="${1}"
    version="${2}"

    url="https://repo1.maven.org/maven2/${artifact}/${version}"
    jar_name="$(basename "$artifact")-${version}.jar"
    md5_name="${jar_name}.md5"

    echo "Downloading ${jar_name}..."
    curl -fsSLo "${jar_name}" "${url}/${jar_name}"
    curl -fsSLo "${md5_name}" "${url}/${md5_name}"

    md5_expected=$(cat "${md5_name}")
    md5_actual=$(md5sum "${jar_name}" | awk '{print $1}')

    if [ "${md5_expected}" != "${md5_actual}" ]; then
        echo "Checksum verification failed for ${jar_name}"
        exit 1
    fi
}