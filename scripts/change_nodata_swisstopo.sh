for filename in /tiles/swissalti3d/**/*.tif; do  # The tiles directory of the mounted volumne in the PG docker container
   tmp_name="$(basename $filename .tif)_new.tif"
   gdalwarp -srcnodata "-9999" -dstnodata "0" "${filename}" "${tmp_name}" && \
   rm $filename && \
   mv $tmp_name $filename
done