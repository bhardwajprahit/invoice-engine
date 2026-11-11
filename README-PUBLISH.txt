INVOICE ENGINE — PUBLIC LAUNCH UPDATE

Included files:
- frontend/index.html: adds Windows download links in navigation, hero and footer.
- frontend/dashboard.html: adds a Finance quick guide inside the in-app tutorial area.
- frontend/invoice-engine-logo.png and frontend/tutorials/: retain the supplied logo, tutorial videos and posters.

Windows installer URL:
https://github.com/bhardwajprahit/invoice-engine/releases/latest/download/Invoice-Engine-Setup-1.0.1.exe

IMPORTANT:
1. This package does not contain or rebuild the Windows installer. The download link points to the existing GitHub Release asset.
2. The supplied public homepage has no Plans/Pricing navigation item or pricing section. No plan page was removed because none was present in this source. If a separate plans page is visible in production, identify its exact route/file before removing it.
3. Preserve frontend/supabase-config.js and all backend/database files.
4. Copy the frontend folder contents into the repository's frontend folder, preserving tutorial subfolder paths. Review changes before committing.
5. Test the download URL, sign-in, dashboard navigation, tutorial playback and Finance page after deployment.
6. The Finance card is a text guide, not a recorded Finance video. Add a dedicated Finance video when one is recorded.
