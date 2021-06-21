#!/usr/bin/env bash

declare -a icons=("camera" "delete" "pause" "open" "play" "reload" "rotate-left"
	"rotate-right" "stop" "reset" "move" "browser" "expand" "file" "calibrate"
	"cube")

size=25

for f in ${icons[@]}; do
	echo -e "\nConverting $f..."
	inkscape -e icons/$f.png -h $size -w $size icons/$f.svg
done

echo -e "\nConverting application icon to png..."
inkscape -e icons/pyhsi.png -h 256 -w 256 icons/pyhsi.svg

echo -e "\nConverting application icon to ico..."
mkdir tmp
declare -a sizes=(16 32 48 128 256)
for s in ${sizes[@]}; do
	inkscape -e tmp/$s.png -h $s -w $s icons/pyhsi.svg
done
convert tmp/16.png tmp/32.png tmp/48.png tmp/128.png tmp/256.png icons/pyhsi.ico
rm -r tmp
