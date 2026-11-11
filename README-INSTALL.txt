INVOICE ENGINE — WEBSITE + TUTORIAL VIDEO UPDATE
=================================================

REPLACEMENT FILES
-----------------
frontend/index.html       Public website
frontend/dashboard.html   Software dashboard
frontend/auth.html        Sign-in / account creation page
frontend/invoice-engine-logo.png
frontend/tutorials/
  invoice-engine-overview.mp4
  invoice-engine-purchasing.mp4
  invoice-engine-billing-sales.mp4
  overview-poster.jpg
  purchasing-poster.jpg
  billing-sales-poster.jpg

INSTALL
-------
1. Back up the current frontend folder.
2. Replace the matching files in your project with the files in this ZIP.
3. Copy the complete frontend/tutorials folder to the same location.
4. Keep your existing frontend/supabase-config.js. It is intentionally not included or changed.
5. Deploy the updated frontend using your normal deployment process.

WHAT CHANGED
------------
- The public website now has real embedded tutorial videos instead of text-only tutorial cards.
- The overview video attempts muted autoplay (browser policy allows muted autoplay); the other two play using their player controls.
- Starting one tutorial pauses the other tutorial players.
- The software dashboard's existing tutorial gallery now points to the actual uploaded MP4 filenames and matching posters.
- The uploaded Invoice Engine logo is used on the website, sign-in page and dashboard.
- Authentication logic in auth.html is preserved.

IMPORTANT NOTES
---------------
- The uploaded index.html did not contain a pricing/plans page or pricing navigation. The uploaded dashboard also had plan-card CSS only; no plan page markup or plan-selection flow was present. Therefore this update does not delete any actual plan-selection logic or hidden page. If the deployed site still shows a plans page, it is likely served by another HTML file or an older deployment; send that exact file/URL and I can remove the correct page without breaking account access.
- There is no bank-reconciliation tutorial video among the supplied MP4s. The three included videos cover overview, Purchasing, and Billing + Sales. Do not present the overview as a bank-reconciliation training video.
- The WAV file in source-assets is the separate 8.57-second original music track supplied with the videos; the MP4s are used directly, so no separate audio playback is required.
- This is a frontend asset update. It does not change API/backend code, database schemas, Supabase settings, or Electron packaging configuration.
- Test the deployed pages in a browser after upload, including video playback, sign-in, and opening the dashboard.
