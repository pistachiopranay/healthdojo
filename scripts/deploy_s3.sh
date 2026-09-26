#!/bin/bash
# Stage site/ + walk traces and publish to the public S3 demo bucket (Pranay's pistachio account).
set -e
cd "$(dirname "$0")/.."
rm -rf .scratch/deploy && cp -R site .scratch/deploy && mkdir -p .scratch/deploy/walks
rsync -a --include='*/' --include='*.jpg' --include='*.json' --exclude='*' data/walks/ .scratch/deploy/walks/
sed -i '' 's#\.\./data/walks/#walks/#g' .scratch/deploy/walk.html
cp docs/pitch/HealthDojo_Pitch.html .scratch/deploy/pitch.html
env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY -u AWS_SESSION_TOKEN AWS_PROFILE=pistachio \
  aws s3 sync .scratch/deploy s3://healthdojo-demo-pear --quiet --delete
echo http://healthdojo-demo-pear.s3-website-us-east-1.amazonaws.com
