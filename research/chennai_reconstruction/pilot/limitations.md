# Pilot limitations

- **Access:** ASF product download returned HTTP 403; no Earthdata credentials are
  configured. CDSE/GEE also require accounts and were not used. No SAR product was
  downloaded.
- **Toolchain:** ESA SNAP `gpt`/`snappy`, `pyroSAR` and `sarpy` are not installed.
  No processing parameters were executed or invented.
- **Boundaries:** the authoritative 2011 GIS (for 2015) and 2018 GIS (for 2021) are not
  available locally under confirmed terms. The 2022 KML was not substituted.
- **Licensing:** OpenCity reports the 2022 KML licence as "not specified"; the GCC
  gazette PDFs have no explicit open-data licence on the inspected page.
- **Pixel quality:** no valid-pixel coverage, border-noise mask, thermal-noise check,
  layover/shadow mask or geolocation diagnostic was produced.
- **Temporal comparison:** nominal metadata compatibility is established, but no
  alignment or change layer was computed.
- **Event chronology:** the 2015 scene is not called a flood-peak observation. No
  inundation label is inferred from low backscatter.
- **Permanent water:** no permanent-water mask was applied; this remains a required
  separate step.
- **2015 vs 2021 boundaries:** different boundary vintages; no cross-version comparison
  is valid without a reviewed crosswalk.
