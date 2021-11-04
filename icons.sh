#!/usr/bin/env bash

declare -a icons=("camera" "delete" "pause" "open" "play" "reload" "rotate-left"
	"rotate-right" "stop" "reset" "move" "browser" "expand" "file" "calibrate"
	"cube" "crop" "network")

size=25
size_hidpi=40
folder="pyhsi/gui/icons"

for f in ${icons[@]}; do
	echo -e "\nConverting $f..."
	inkscape --export-png $folder/$f$size.png -h $size -w $size $folder/$f.svg
	inkscape --export-png $folder/$f$size_hidpi.png -h $size_hidpi -w $size_hidpi $folder/$f.svg
done

echo -e "\nConverting application icon to png..."
inkscape --export-png $folder/pyhsi.png -h 256 -w 256 $folder/pyhsi.svg

echo -e "\nConverting application icon to ico..."
mkdir tmp
declare -a sizes=(16 32 48 128 256)
for s in ${sizes[@]}; do
	inkscape --export-png tmp/$s.png -h $s -w $s $folder/pyhsi.svg
done
convert tmp/16.png tmp/32.png tmp/48.png tmp/128.png tmp/256.png $folder/pyhsi.ico
rm -r tmp
