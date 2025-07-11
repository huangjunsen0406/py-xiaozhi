#!/usr/bin/env bash
#export DYLD_LIBRARY_PATH=/opt/homebrew/Cellar/opus/1.5.2/lib
export DYLD_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_LIBRARY_PATH
echo "Opus version:"
brew list --versions opus

echo "Libopus path:"
ls /opt/homebrew/Cellar/opus/1.5.2/lib

echo "DYLD_LIBRARY_PATH=$DYLD_LIBRARY_PATH"

echo "Try running opuslib:"
python3 -c "import opuslib; print('Opus OK')"