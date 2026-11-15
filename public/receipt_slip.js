/**
 * Rolea Topup - Official Receipt Slip Generator
 * Generates high-resolution PNG receipt slips for orders
 * Pure HTML5 Canvas 2D - Zero external dependencies - No emojis
 */
(function() {
  'use strict';

  async function generateSlipCanvas(order, storeSettings = {}) {
    const scale = 2; // High-DPI scale for sharp rendering on mobile and retina screens
    const width = 560;
    const height = 820;

    const canvas = document.createElement('canvas');
    canvas.width = width * scale;
    canvas.height = height * scale;
    const ctx = canvas.getContext('2d');
    ctx.scale(scale, scale);

    const storeName = storeSettings.store_name || 'ROLEA TOPUP';
    const storeLogoUrl = storeSettings.store_logo || '/media/logo.webp';
    const orderId = order.order_id || 'ORD-000000';
    const amountVal = '$' + Number(order.amount || 0).toFixed(2) + ' USD';
    const productName = String(order.package || order.product_name || 'Robux Topup').trim();
    const username = '@' + String(order.roblox_username || order.display_name || order.user_id || 'Customer').replace(/^@/, '');
    const dateStr = order.created_at ? new Date(order.created_at).toLocaleString('en-GB', { hour12: false }) : new Date().toLocaleString('en-GB', { hour12: false });
    const isPaid = order.paid || order.status === 'completed' || order.status === 'paid' || order.delivered;
    const isDelivered = order.delivered || order.status === 'completed';
    const isRefunded = order.status === 'refunded';

    // 1. Background
    ctx.fillStyle = '#f8fafc';
    ctx.fillRect(0, 0, width, height);

    // Card Container with rounded corners
    const pad = 20;
    const cw = width - pad * 2;
    const ch = height - pad * 2;
    const cr = 20;

    ctx.save();
    ctx.beginPath();
    ctx.roundRect(pad, pad, cw, ch, cr);
    ctx.fillStyle = '#ffffff';
    ctx.shadowColor = 'rgba(15, 23, 42, 0.08)';
    ctx.shadowBlur = 24;
    ctx.shadowOffsetY = 8;
    ctx.fill();
    ctx.strokeStyle = '#e2e8f0';
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.restore();

    // 2. Top Header Accent Banner
    ctx.save();
    ctx.beginPath();
    ctx.roundRect(pad, pad, cw, 100, [cr, cr, 0, 0]);
    const grad = ctx.createLinearGradient(pad, pad, pad + cw, pad + 100);
    grad.addColorStop(0, '#0284c7');
    grad.addColorStop(1, '#0369a1');
    ctx.fillStyle = grad;
    ctx.fill();

    // Store Name & Subtitle
    ctx.fillStyle = '#ffffff';
    ctx.font = '800 20px "Plus Jakarta Sans", -apple-system, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(storeName.toUpperCase(), width / 2, pad + 42);

    ctx.font = '600 11.5px "Inter", -apple-system, sans-serif';
    ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
    ctx.fillText('OFFICIAL TRANSACTION RECEIPT', width / 2, pad + 64);

    // Decorative Verified Tag
    ctx.font = '700 10px "Inter", -apple-system, sans-serif';
    ctx.fillStyle = 'rgba(255, 255, 255, 0.75)';
    ctx.fillText('VERIFIED VIA BAKONG KHQR', width / 2, pad + 82);
    ctx.restore();

    // 3. Status Circle Badge
    const circleY = pad + 100;
    ctx.save();
    ctx.beginPath();
    ctx.arc(width / 2, circleY, 26, 0, Math.PI * 2);
    ctx.fillStyle = isRefunded ? '#dc2626' : (isDelivered ? '#10b981' : '#0284c7');
    ctx.shadowColor = isRefunded ? 'rgba(220, 38, 38, 0.35)' : 'rgba(16, 185, 129, 0.35)';
    ctx.shadowBlur = 12;
    ctx.fill();
    ctx.lineWidth = 4;
    ctx.strokeStyle = '#ffffff';
    ctx.stroke();

    // Draw checkmark or cross inside badge
    ctx.beginPath();
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 3.2;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    if (isRefunded) {
      // Draw X
      ctx.moveTo(width / 2 - 8, circleY - 8);
      ctx.lineTo(width / 2 + 8, circleY + 8);
      ctx.moveTo(width / 2 + 8, circleY - 8);
      ctx.lineTo(width / 2 - 8, circleY + 8);
    } else {
      // Draw checkmark
      ctx.moveTo(width / 2 - 9, circleY);
      ctx.lineTo(width / 2 - 2, circleY + 7);
      ctx.lineTo(width / 2 + 9, circleY - 6);
    }
    ctx.stroke();
    ctx.restore();

    // 4. Amount Box
    let curY = circleY + 44;
    ctx.textAlign = 'center';
    ctx.fillStyle = '#64748b';
    ctx.font = '700 11px "Inter", sans-serif';
    ctx.fillText('AMOUNT PAID', width / 2, curY);

    curY += 34;
    ctx.fillStyle = '#0f172a';
    ctx.font = '900 32px "Plus Jakarta Sans", sans-serif';
    ctx.fillText(amountVal, width / 2, curY);

    curY += 20;
    ctx.fillStyle = isRefunded ? '#dc2626' : '#059669';
    ctx.font = '800 12px "Inter", sans-serif';
    const statusText = isRefunded ? 'REFUNDED TO ROLEA WALLET' : (isDelivered ? 'PAYMENT CONFIRMED & DELIVERED' : 'PAYMENT CONFIRMED (PROCESSING)');
    ctx.fillText(statusText, width / 2, curY);

    // 5. Dashed Divider Line
    curY += 22;
    drawDashedLine(ctx, pad + 24, curY, width - pad - 24, curY);

    // 6. Details Table
    curY += 28;
    const details = [
      ['Order ID', orderId, true],
      ['Product / Service', productName, false],
      ['Roblox Account', username, false],
      ['Payment Method', 'ABA KHQR / Wallet', false],
      ['Transaction Date', dateStr, false],
      ['Support Channel', '@' + (storeSettings.telegram_handle || 'Rothzz3'), false]
    ];

    const leftX = pad + 28;
    const rightX = width - pad - 28;

    for (const [label, val, isMono] of details) {
      ctx.textAlign = 'left';
      ctx.fillStyle = '#64748b';
      ctx.font = '600 12.5px "Inter", sans-serif';
      ctx.fillText(label, leftX, curY);

      ctx.textAlign = 'right';
      ctx.fillStyle = '#0f172a';
      ctx.font = isMono
        ? '700 12.5px "JetBrains Mono", Consolas, monospace'
        : '700 12.5px "Plus Jakarta Sans", sans-serif';
      
      // Trim if too long
      let displayVal = val;
      if (ctx.measureText(displayVal).width > 240) {
        while (displayVal.length > 3 && ctx.measureText(displayVal + '...').width > 240) {
          displayVal = displayVal.slice(0, -1);
        }
        displayVal += '...';
      }
      ctx.fillText(displayVal, rightX, curY);

      curY += 29;
    }

    // 7. Second Dashed Divider
    curY += 2;
    drawDashedLine(ctx, pad + 24, curY, width - pad - 24, curY);

    // 8. Footer & Verification Box
    curY += 26;
    ctx.textAlign = 'center';
    ctx.fillStyle = '#0f172a';
    ctx.font = '800 12px "Plus Jakarta Sans", sans-serif';
    ctx.fillText('Thank you for trusting ' + storeName + '!', width / 2, curY);

    curY += 18;
    ctx.fillStyle = '#64748b';
    ctx.font = '500 11px "Inter", sans-serif';
    ctx.fillText('Safe, instant, and automated game top-up in Cambodia.', width / 2, curY);

    // Verification Bar Code / QR placeholder box
    curY += 20;
    const barBoxW = 280;
    const barBoxH = 38;
    const barBoxX = (width - barBoxW) / 2;
    ctx.save();
    ctx.beginPath();
    ctx.roundRect(barBoxX, curY, barBoxW, barBoxH, 8);
    ctx.fillStyle = '#f1f5f9';
    ctx.fill();
    ctx.strokeStyle = '#e2e8f0';
    ctx.lineWidth = 1;
    ctx.stroke();

    ctx.textAlign = 'center';
    ctx.fillStyle = '#475569';
    ctx.font = '700 10.5px "JetBrains Mono", Consolas, monospace';
    ctx.fillText('VERIFY: ' + orderId, width / 2, curY + 23);
    ctx.restore();

    curY += barBoxH + 20;
    ctx.textAlign = 'center';
    ctx.fillStyle = '#94a3b8';
    ctx.font = '600 9.5px "Inter", sans-serif';
    ctx.fillText('DIGITAL SLIP GENERATED SECURELY BY ROLEA SYSTEM', width / 2, curY);

    return canvas;
  }

  function drawDashedLine(ctx, x1, y1, x2, y2) {
    ctx.save();
    ctx.beginPath();
    ctx.setLineDash([5, 4]);
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.strokeStyle = '#e2e8f0';
    ctx.lineWidth = 1.2;
    ctx.stroke();
    ctx.restore();
  }

  // Public API
  window.RoleaSlip = {
    download: async function(order, storeSettings = {}) {
      if (!order || !order.order_id) {
        alert('Invalid order data for receipt slip.');
        return;
      }

      const canvas = await generateSlipCanvas(order, storeSettings);
      
      // Convert to blob and download
      canvas.toBlob(function(blob) {
        if (!blob) {
          alert('Failed to generate receipt image.');
          return;
        }
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = 'Receipt-' + String(order.order_id).replace(/[^a-zA-Z0-9_-]/g, '') + '.png';
        document.body.appendChild(a);
        a.click();
        setTimeout(function() {
          document.body.removeChild(a);
          URL.revokeObjectURL(url);
        }, 1500);
      }, 'image/png', 0.95);
    }
  };
})();
