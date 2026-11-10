const path = require('path');
const fs = require('fs');
const publicDir = path.join(__dirname, 'public');

['index.html', 'roblox.html', 'mlbb.html', 'tiktok.html', 'freefire.html', 'check_order.html', 'receipt.html'].forEach(f => {
  const p = path.join(publicDir, f);
  console.log(f, fs.existsSync(p) ? 'EXISTS (' + fs.statSync(p).size + 'B)' : 'MISSING');
});
