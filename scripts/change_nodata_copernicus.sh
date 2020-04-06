for filename in /tiles/copernicus/*.TIF; do  # The tiles directory of the mounted volumne in the PG docker container
   tmp_name="$(basename $filename .TIF)_new.TIF"
   gdalwarp -srcnodata "-3.4028234663852886e+38" -dstnodata "0" "${filename}" "${tmp_name}" && \
   rm $filename && \
   mv $tmp_name $filename
done