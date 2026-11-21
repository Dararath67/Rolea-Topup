/**
 * Rolea Topup - Pure Vector Winter Snowfall Effect (100% Real Crisp Snowflakes, No AI, No Cartoons)
 * GPU-Accelerated 60fps HTML5 Canvas with Pre-rendered High-DPI Vector Sprites
 */
(function () {
  if (window.__roleaSnowInit) return;
  window.__roleaSnowInit = true;

  // Respect user preference for reduced motion
  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    return;
  }

  var canvas, ctx;
  var width = window.innerWidth || 1200;
  var height = window.innerHeight || 800;
  var particles = [];
  var animFrameId = null;
  var isRunning = false;

  var isMobile = (window.innerWidth < 768) || /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
  var PARTICLE_COUNT = isMobile ? 32 : 65;

  // Pre-rendered offscreen sprite cache for 60fps GPU performance
  var sprites = [];

  function createSnowflakeSprite(type, size) {
    var offCanvas = document.createElement('canvas');
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var pad = 6;
    var totalSize = (size + pad * 2) * dpr;
    offCanvas.width = totalSize;
    offCanvas.height = totalSize;
    var oCtx = offCanvas.getContext('2d');
    oCtx.scale(dpr, dpr);

    var cx = size / 2 + pad;
    var cy = size / 2 + pad;
    var r = size / 2;

    oCtx.save();
    oCtx.shadowColor = 'rgba(255, 255, 255, 0.7)';
    oCtx.shadowBlur = 3;

    if (type === 'stellar') {
      // Classic 6-branch stellar dendrite crystal snowflake
      oCtx.strokeStyle = 'rgba(255, 255, 255, 0.95)';
      oCtx.lineWidth = 1.35;
      oCtx.lineCap = 'round';

      for (var i = 0; i < 6; i++) {
        var a = i * (Math.PI / 3);
        var cos = Math.cos(a);
        var sin = Math.sin(a);

        // Main spine
        oCtx.beginPath();
        oCtx.moveTo(cx, cy);
        oCtx.lineTo(cx + cos * r, cy + sin * r);
        oCtx.stroke();

        // Outer V-branches at 75% length
        var bx1 = cx + cos * (r * 0.72);
        var by1 = cy + sin * (r * 0.72);
        for (var side = -1; side <= 1; side += 2) {
          var ba1 = a + side * (Math.PI / 3.8);
          oCtx.beginPath();
          oCtx.moveTo(bx1, by1);
          oCtx.lineTo(bx1 + Math.cos(ba1) * (r * 0.28), by1 + Math.sin(ba1) * (r * 0.28));
          oCtx.stroke();
        }

        // Inner V-branches at 46% length
        var bx2 = cx + cos * (r * 0.46);
        var by2 = cy + sin * (r * 0.46);
        for (var side2 = -1; side2 <= 1; side2 += 2) {
          var ba2 = a + side2 * (Math.PI / 3.6);
          oCtx.beginPath();
          oCtx.moveTo(bx2, by2);
          oCtx.lineTo(bx2 + Math.cos(ba2) * (r * 0.22), by2 + Math.sin(ba2) * (r * 0.22));
          oCtx.stroke();
        }
      }

      // Small central crystal nucleus
      oCtx.fillStyle = 'rgba(255, 255, 255, 0.95)';
      oCtx.beginPath();
      oCtx.arc(cx, cy, 1.8, 0, Math.PI * 2);
      oCtx.fill();

    } else if (type === 'crystal') {
      // 6-point star with delicate diamond tipped points
      oCtx.strokeStyle = 'rgba(255, 255, 255, 0.9)';
      oCtx.lineWidth = 1.2;
      oCtx.lineCap = 'round';

      for (var j = 0; j < 6; j++) {
        var a2 = j * (Math.PI / 3);
        var cos2 = Math.cos(a2);
        var sin2 = Math.sin(a2);

        oCtx.beginPath();
        oCtx.moveTo(cx, cy);
        oCtx.lineTo(cx + cos2 * r, cy + sin2 * r);
        oCtx.stroke();

        // Single delicate chevron near the tip
        var px = cx + cos2 * (r * 0.65);
        var py = cy + sin2 * (r * 0.65);
        for (var s = -1; s <= 1; s += 2) {
          var sa = a2 + s * (Math.PI / 4);
          oCtx.beginPath();
          oCtx.moveTo(px, py);
          oCtx.lineTo(px + Math.cos(sa) * (r * 0.2), py + Math.sin(sa) * (r * 0.2));
          oCtx.stroke();
        }
      }

      oCtx.fillStyle = 'rgba(255, 255, 255, 0.9)';
      oCtx.beginPath();
      oCtx.arc(cx, cy, 1.4, 0, Math.PI * 2);
      oCtx.fill();

    } else {
      // Soft glowing round snow pellet (dot)
      var grad = oCtx.createRadialGradient(cx, cy, 0, cx, cy, r);
      grad.addColorStop(0, 'rgba(255, 255, 255, 0.98)');
      grad.addColorStop(0.5, 'rgba(240, 248, 255, 0.85)');
      grad.addColorStop(1, 'rgba(255, 255, 255, 0)');

      oCtx.fillStyle = grad;
      oCtx.beginPath();
      oCtx.arc(cx, cy, r, 0, Math.PI * 2);
      oCtx.fill();
    }

    oCtx.restore();

    return {
      canvas: offCanvas,
      renderSize: size + pad * 2,
      halfSize: (size + pad * 2) / 2
    };
  }

  function initSprites() {
    sprites = [
      createSnowflakeSprite('stellar', 24), // Sprite 0: Large stellar snowflake
      createSnowflakeSprite('stellar', 18), // Sprite 1: Medium stellar snowflake
      createSnowflakeSprite('crystal', 15), // Sprite 2: Crystal star snowflake
      createSnowflakeSprite('crystal', 11), // Sprite 3: Small crystal snowflake
      createSnowflakeSprite('dot', 7),     // Sprite 4: Medium soft glowing snow dot
      createSnowflakeSprite('dot', 4.5),   // Sprite 5: Small soft snow dot
      createSnowflakeSprite('dot', 3)      // Sprite 6: Tiny atmospheric snow speck
    ];
  }

  function createParticle(initialY) {
    // 45% geometric snowflakes, 55% soft snow pellets & specks (just like real winter snowfall)
    var isSnowflake = Math.random() < 0.45;
    var spriteIdx;

    if (isSnowflake) {
      // Pick one of the stellar or crystal snowflake sprites (0..3)
      var pick = Math.random();
      if (pick < 0.25) spriteIdx = 0;       // Large stellar
      else if (pick < 0.55) spriteIdx = 1;  // Medium stellar
      else if (pick < 0.8) spriteIdx = 2;   // Crystal star
      else spriteIdx = 3;                  // Small crystal
    } else {
      // Pick one of the soft snow dots (4..6)
      var pickDot = Math.random();
      if (pickDot < 0.35) spriteIdx = 4;
      else if (pickDot < 0.75) spriteIdx = 5;
      else spriteIdx = 6;
    }

    // 3D Parallax Depth: Layer 1 (background), Layer 2 (midground), Layer 3 (foreground)
    var depth = (spriteIdx === 0 || spriteIdx === 4) ? 3 : ((spriteIdx === 1 || spriteIdx === 2 || spriteIdx === 5) ? 2 : 1);

    var speedY = depth === 3 ? (Math.random() * 0.9 + 1.2) : (depth === 2 ? (Math.random() * 0.7 + 0.8) : (Math.random() * 0.5 + 0.5));
    var opacity = depth === 3 ? (Math.random() * 0.25 + 0.7) : (depth === 2 ? (Math.random() * 0.3 + 0.5) : (Math.random() * 0.25 + 0.3));

    return {
      x: Math.random() * width,
      y: (initialY !== undefined) ? initialY : (Math.random() * height),
      spriteIdx: spriteIdx,
      speedY: speedY,
      swaySpeed: Math.random() * 0.02 + 0.008,
      swayRange: Math.random() * 1.4 + 0.5,
      angle: Math.random() * Math.PI * 2,
      rotation: Math.random() * Math.PI * 2,
      rotationSpeed: isSnowflake ? ((Math.random() - 0.5) * 0.02) : 0,
      opacity: opacity
    };
  }

  function initCanvas() {
    canvas = document.createElement('canvas');
    canvas.id = 'rolea-snow-canvas';
    canvas.setAttribute('aria-hidden', 'true');
    canvas.style.position = 'fixed';
    canvas.style.top = '0';
    canvas.style.left = '0';
    canvas.style.width = '100vw';
    canvas.style.height = '100vh';
    canvas.style.pointerEvents = 'none';
    canvas.style.userSelect = 'none';
    canvas.style.webkitUserSelect = 'none';
    canvas.style.zIndex = '99998';
    canvas.style.opacity = '1';
    canvas.style.transition = 'opacity .4s ease';

    ctx = canvas.getContext('2d');
    initSprites();
    resize();

    particles = [];
    for (var i = 0; i < PARTICLE_COUNT; i++) {
      particles.push(createParticle(Math.random() * height));
    }

    document.body.appendChild(canvas);
    start();

    window.addEventListener('resize', onResize, { passive: true });
    document.addEventListener('visibilitychange', onVisibilityChange);
  }

  function resize() {
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);
  }

  var resizeTimeout;
  function onResize() {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(resize, 100);
  }

  function onVisibilityChange() {
    if (document.hidden) {
      stop();
    } else {
      start();
    }
  }

  function render() {
    ctx.clearRect(0, 0, width, height);

    for (var i = 0; i < particles.length; i++) {
      var p = particles[i];

      // Physics update
      p.angle += p.swaySpeed;
      p.x += Math.sin(p.angle) * p.swayRange;
      p.y += p.speedY;
      p.rotation += p.rotationSpeed;

      // Wrap-around
      if (p.y > height + 30) {
        p.y = -30;
        p.x = Math.random() * width;
      }
      if (p.x < -35) p.x = width + 25;
      if (p.x > width + 35) p.x = -25;

      var spr = sprites[p.spriteIdx];
      if (!spr) continue;

      ctx.save();
      ctx.globalAlpha = p.opacity;
      ctx.translate(p.x, p.y);

      if (p.rotationSpeed !== 0) {
        ctx.rotate(p.rotation);
      }

      // Draw high-performance hardware-accelerated sprite
      ctx.drawImage(spr.canvas, -spr.halfSize, -spr.halfSize, spr.renderSize, spr.renderSize);
      ctx.restore();
    }

    if (isRunning) {
      animFrameId = requestAnimationFrame(render);
    }
  }

  function start() {
    if (isRunning) return;
    isRunning = true;
    animFrameId = requestAnimationFrame(render);
  }

  function stop() {
    isRunning = false;
    if (animFrameId) {
      cancelAnimationFrame(animFrameId);
      animFrameId = null;
    }
  }

  function toggle() {
    if (!canvas) return;
    if (isRunning) {
      canvas.style.opacity = '0';
      setTimeout(stop, 400);
    } else {
      canvas.style.opacity = '1';
      start();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCanvas, { once: true });
  } else {
    initCanvas();
  }

  window.RoleaSnow = {
    start: start,
    stop: stop,
    toggle: toggle,
    setDensity: function (count) {
      PARTICLE_COUNT = count;
      particles = [];
      for (var i = 0; i < count; i++) {
        particles.push(createParticle());
      }
    }
  };
})();
