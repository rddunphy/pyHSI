#!/usr/bin/env bash

declare -a icons=("camera" "delete" "pause" "open" "play" "reload" "rotate-left" "rotate-right" "stop" "reset" "move")
size=25

for f in ${icons[@]}; do
	echo "Converting $f..."
	inkscape -e icons/$f.png -h $size -w $size icons/$f.svg
done
