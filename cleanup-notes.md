# Image Cleanup Notes

## What was done

32 PNG files with gray backgrounds (visible when printed, subtle on screen) were
cleaned using ImageMagick's sigmoidal contrast filter. The cleaned versions replace
the originals. Originals are backed up in `originals_backup/`.

## Why sigmoidal contrast

Hard thresholding (`-threshold 65%`) removed gray backgrounds but broke thin notation
lines (dark-gray lines fell below the cutoff and became intermittent). Sigmoidal
contrast boosts contrast gradually, whitening light backgrounds while preserving
dark notation pixels.

## Command used

```bash
convert INPUT.png -colorspace Gray -sigmoidal-contrast 5,50% OUTPUT.png
```

## To reproduce for a single file

```bash
convert "Fisher's Hornpipe.png" -colorspace Gray -sigmoidal-contrast 5,50% "Fisher's Hornpipe.png"
```

## To reproduce for all 32 files

```bash
cd /home/porter/Documents/banjo/WOFTA/combined_book/6

for f in \
  "Eighth of January.png" "Little Burnt Potato.png" "Fisher's Hornpipe.png" \
  "Pretty Little Dog (old).png" "Centralia Waltz.png" "Elmer's Waltz.png" \
  "My Darling Asleep.png" "Kerry Mills' Barn Dance.png" "Needle Case.png" \
  "Liberty.png" "Honest John.png" "Spotted Dog (old).png" \
  "Clearwater Stomp.png" "Star of the County Down (in 4-4).png" \
  "Miss McCloud's Reel.png" "Sarah Armstrong.png" "New Five Cent Piece.png" \
  "Laura Susan.png" "Demented Dog (old), The.png" "Over the Waterfall.png" \
  "Boggy Road to Texas, The.png" "Kittens on Catnip (old).png" "Hey Polka.png" \
  "Cindy.png" "Skippin' Cat (old).png" "Off to California.png" \
  "Cat on a Leash (old).png" "Border Collie (old).png" \
  "Cat in the Hopper (old).png" "Granny Will Your Dog Bite (old).png" \
  "Bull Moose.png" "Boys of Blue Hill, The.png"; do
  convert "$f" -colorspace Gray -sigmoidal-contrast 5,50% "$f"
done
```

## How files were identified

Pixel analysis using ImageMagick's `-fx` operator to count pixels in the mid-gray
range (40–94% brightness) — neither pure white background nor black notation.
Files with more than ~13% of pixels in that range were flagged as needing cleanup.

```bash
for f in *.png; do
  gray_pct=$(convert "$f" -colorspace Gray \
    -fx "(u>0.40 && u<0.94) ? 1 : 0" \
    -format "%[fx:mean*100]" info:)
  echo "$gray_pct $f"
done | sort -rn
```
