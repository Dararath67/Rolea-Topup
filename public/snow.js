/**
 * Rolea Topup - Festive Winter Snowfall Effect
 * High-performance 60fps canvas snow with 3D parallax depth, rotation, and gentle wind sway.
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

  // Symbols to draw: snowflakes, crystals, soft dots, and occasional snowman
  var ICONS = ['❄', '❅', '✻', '❄', '❅', '⛄'];

  var isMobile = (window.innerWidth < 768) || /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
  var PARTICLE_COUNT = isMobile ? 26 : 55;

  function createParticle(initialY) {
    var sizeCategory = Math.random();
    var isIcon = Math.random() > 0.38;
    var icon = ICONS[Math.floor(Math.random() * ICONS.length)];
    
    // Depth layer: 1 (far/slow/small), 2 (mid), 3 (close/fast/large)
    var layer = sizeCategory < 0.5 ? 1 : (sizeCategory < 0.85 ? 2 : 3);
    var size = layer === 1 ? (Math.random() * 5 + 7) : (layer === 2 ? (Math.random() * 8 + 12) : (Math.random() * 10 + 18));
    var speedY = layer === 1 ? (Math.random() * 0.7 + 0.6) : (layer === 2 ? (Math.random() * 1.1 + 1.0) : (Math.random() * 1.4 + 1.5));
    var opacity = layer === 1 ? (Math.random() * 0.25 + 0.35) : (layer === 2 ? (Math.random() * 0.3 + 0.55) : (Math.random() * 0.3 + 0.7));

    return {
      x: Math.random() * width,
      y: (initialY !== undefined) ? initialY : (Math.random() * height),
      layer: layer,
      size: size,
      speedY: speedY,
      swaySpeed: Math.random() * 0.02 + 0.01,
      swayRange: Math.random() * 1.5 + 0.5,
      angle: Math.random() * Math.PI * 2,
      rotation: Math.random() * Math.PI * 2,
      rotationSpeed: (Math.random() - 0.5) * 0.03,
      isIcon: isIcon,
      icon: icon,
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
    canvas.style.zIndex = '99998'; // Just below preloader, above page content
    canvas.style.opacity = '1';
    canvas.style.transition = 'opacity .4s ease';

    ctx = canvas.getContext('2d');
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
    var dpr = window.devicePixelRatio || 1;
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);
  }

  var resizeTimeout;
  function onResize() {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(resize, 120);
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

      // Update positions
      p.angle += p.swaySpeed;
      p.x += Math.sin(p.angle) * p.swayRange;
      p.y += p.speedY;
      p.rotation += p.rotationSpeed;

      // Wrap around edges
      if (p.y > height + 25) {
        p.y = -25;
        p.x = Math.random() * width;
      }
      if (p.x < -30) p.x = width + 20;
      if (p.x > width + 30) p.x = -20;

      // Draw particle
      ctx.save();
      ctx.globalAlpha = p.opacity;

      if (p.isIcon) {
        ctx.translate(p.x, p.y);
        ctx.rotate(p.rotation);
        ctx.font = Math.round(p.size) + 'px "Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji", sans-serif';
        ctx.fillStyle = '#ffffff';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.shadowColor = 'rgba(255, 255, 255, 0.45)';
        ctx.shadowBlur = 4;
        ctx.fillText(p.icon, 0, 0);
      } else {
        // Soft glowing snow dot
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size / 3.2, 0, Math.PI * 2);
        ctx.fillStyle = '#ffffff';
        ctx.shadowColor = 'rgba(255, 255, 255, 0.6)';
        ctx.shadowBlur = 6;
        ctx.fill();
      }

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

  // Auto initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCanvas, { once: true });
  } else {
    initCanvas();
  }

  // Public controls
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
