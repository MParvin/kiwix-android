#!/usr/bin/env bash
# Ensure the Gradle wrapper distribution is fully cached under ~/.gradle/wrapper/dists.
# Downloads from GRADLE_MIRROR (default: Tencent) when services.gradle.org is flaky.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROP="${ROOT}/gradle/wrapper/gradle-wrapper.properties"
MIRROR="${GRADLE_MIRROR:-https://mirrors.cloud.tencent.com/gradle}"

URL=$(grep -E '^distributionUrl=' "$PROP" | cut -d= -f2- | sed 's/\\//g')
ZIP=$(basename "$URL")
VER=$(echo "$ZIP" | sed -E 's/gradle-([0-9.]+)-bin\.zip/\1/')
BASE="${HOME}/.gradle/wrapper/dists/gradle-${VER}-bin"

if find "$BASE" -type f -path "*/gradle-${VER}/bin/gradle" 2>/dev/null | grep -q .; then
  echo "Gradle ${VER} already cached under ${BASE}"
  exit 0
fi

echo "Gradle ${VER} not cached; downloading on host..."
HASH=$(URL="$URL" python3 -c 'import hashlib,os;n=int.from_bytes(hashlib.md5(os.environ["URL"].encode()).digest(),"big");d="0123456789abcdefghijklmnopqrstuvwxyz";s="";
while n:
 n,r=divmod(n,36);s=d[r]+s
print(s or "0")')

DEST="${BASE}/${HASH}"
mkdir -p "$DEST"
cd "$DEST"
MIRROR_URL="${MIRROR}/${ZIP}"

if command -v wget >/dev/null; then
  wget --continue --tries=10 --timeout=60 --read-timeout=60 -O "$ZIP" "$MIRROR_URL" \
    || wget --continue --tries=10 --timeout=60 --read-timeout=60 -O "$ZIP" "$URL"
else
  curl -fL --retry 10 --retry-all-errors --retry-delay 2 -C - -o "$ZIP" "$MIRROR_URL" \
    || curl -fL --retry 10 --retry-all-errors --retry-delay 2 -C - -o "$ZIP" "$URL"
fi

unzip -t "$ZIP" >/dev/null
rm -rf "gradle-${VER}"
unzip -q "$ZIP"
touch "${ZIP}.lck" "${ZIP}.ok"
test -x "gradle-${VER}/bin/gradle"
echo "Gradle ${VER} cached at ${DEST}"
