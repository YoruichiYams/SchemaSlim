import React, { useEffect, useRef } from 'react';

interface ConstellationGridProps {
  className?: string;
  gridSpacing?: number;
  mouseRadius?: number;
}

interface Node {
  baseX: number;
  baseY: number;
  x: number;
  y: number;
  vx: number;
  vy: number;
  hexId: string;
}

interface Wave {
  x: number;
  y: number;
  radius: number;
  maxRadius: number;
  speed: number;
  intensity: number;
}

export const ConstellationGrid: React.FC<ConstellationGridProps> = ({
  className = '',
  gridSpacing = 52,
  mouseRadius = 140,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId = 0;
    let width = 0;
    let height = 0;
    let isVisible = true;
    let lastTime = performance.now();

    let nodes: Node[] = [];
    let waves: Wave[] = [];
    const mouse = { x: -9999, y: -9999, isActive: false };

    // Physical constants (Hooke's Law & Damping)
    const springK = 0.045; // Spring stiffness
    const damping = 0.86;  // Velocity retention
    const repelStrength = 4.2; // Cursor repulsion force

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = rect.width;
      height = rect.height;

      canvas.width = width * dpr;
      canvas.height = height * dpr;
      ctx.scale(dpr, dpr);

      initGrid();
    };

    const initGrid = () => {
      nodes = [];
      const cols = Math.ceil(width / gridSpacing) + 1;
      const rows = Math.ceil(height / gridSpacing) + 1;

      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          const bx = c * gridSpacing;
          const by = r * gridSpacing;
          // Deterministic hex ID for coordinate label
          const hex = ((c * 17 + r * 31) % 256).toString(16).toUpperCase().padStart(2, '0');

          nodes.push({
            baseX: bx,
            baseY: by,
            x: bx,
            y: by,
            vx: 0,
            vy: 0,
            hexId: hex,
          });
        }
      }
    };

    const handleMouseMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      mouse.x = e.clientX - rect.left;
      mouse.y = e.clientY - rect.top;
      mouse.isActive = true;
    };

    const handleMouseLeave = () => {
      mouse.isActive = false;
      mouse.x = -9999;
      mouse.y = -9999;
    };

    const handleClick = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      const clickX = e.clientX - rect.left;
      const clickY = e.clientY - rect.top;

      waves.push({
        x: clickX,
        y: clickY,
        radius: 0,
        maxRadius: 260,
        speed: 5.5,
        intensity: 8.0,
      });
    };

    window.addEventListener('mousemove', handleMouseMove, { passive: true });
    document.addEventListener('mouseleave', handleMouseLeave);
    canvas.addEventListener('click', handleClick);

    const resizeObserver = new ResizeObserver(() => resize());
    resizeObserver.observe(canvas);
    resize();

    // Pause physics/rendering when off-screen to save 100% GPU/CPU
    const intersectionObserver = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        isVisible = entry.isIntersecting;
        if (isVisible) {
          lastTime = performance.now();
          if (!animationFrameId) {
            animationFrameId = requestAnimationFrame(render);
          }
        }
      }
    });
    intersectionObserver.observe(canvas);

    // Radar scanner animation state
    let radarAngle = 0;
    let radarPulseRadius = 0;

    // Main animation loop with deltaTime normalization
    const render = (timestamp: number) => {
      if (!isVisible) {
        animationFrameId = 0;
        return;
      }

      // Delta time normalization relative to 60fps baseline
      const elapsed = Math.min((timestamp - lastTime) / 1000, 0.1);
      lastTime = timestamp;
      const timeScale = elapsed / (1 / 60); // 1.0 on 60Hz, 0.5 on 120Hz

      ctx.clearRect(0, 0, width, height);

      radarAngle += 0.025 * timeScale;
      radarPulseRadius = (radarPulseRadius + 0.45 * timeScale) % (mouseRadius * 0.75);

      // Update kinetic waves
      const waveDecay = Math.pow(0.96, timeScale);
      for (let i = waves.length - 1; i >= 0; i--) {
        const w = waves[i];
        w.radius += w.speed * timeScale;
        w.intensity *= waveDecay;
        if (w.radius > w.maxRadius || w.intensity < 0.1) {
          waves.splice(i, 1);
        }
      }

      let closestNode: Node | null = null;
      let minDistance = Infinity;

      // Effective damping power for current refresh rate (prevents over-damping on 120Hz+)
      const effectiveDamping = Math.pow(damping, timeScale);

      // Update physics for each node
      for (let i = 0; i < nodes.length; i++) {
        const n = nodes[i];

        // 1. Hooke's Law: F = -k * dx
        const springFx = (n.baseX - n.x) * springK;
        const springFy = (n.baseY - n.y) * springK;

        let totalFx = springFx;
        let totalFy = springFy;

        // 2. Cursor Repulsion
        if (mouse.isActive) {
          const mdx = n.x - mouse.x;
          const mdy = n.y - mouse.y;
          const dist = Math.sqrt(mdx * mdx + mdy * mdy);

          if (dist < minDistance) {
            minDistance = dist;
            closestNode = n;
          }

          if (dist < mouseRadius && dist > 0.001) {
            const factor = (1 - dist / mouseRadius) * repelStrength;
            totalFx += (mdx / dist) * factor;
            totalFy += (mdy / dist) * factor;
          }
        }

        // 3. Kinetic Wave Displacement
        for (let j = 0; j < waves.length; j++) {
          const w = waves[j];
          const wdx = n.x - w.x;
          const wdy = n.y - w.y;
          const wdist = Math.sqrt(wdx * wdx + wdy * wdy);
          const diff = Math.abs(wdist - w.radius);

          if (diff < 30 && wdist > 0.001) {
            const wavePush = (1 - diff / 30) * w.intensity;
            totalFx += (wdx / wdist) * wavePush;
            totalFy += (wdy / wdist) * wavePush;
          }
        }

        // Integrate velocity & position with normalized deltaTime
        n.vx = (n.vx + totalFx * timeScale) * effectiveDamping;
        n.vy = (n.vy + totalFy * timeScale) * effectiveDamping;
        n.x += n.vx * timeScale;
        n.y += n.vy * timeScale;
      }

      // Draw Connection Lines with DRAW CALL BATCHING
      // Instead of 1100+ separate beginPath/stroke calls, we batch all regular lines into ONE single stroke call!
      const cols = Math.ceil(width / gridSpacing) + 1;
      const rows = Math.ceil(height / gridSpacing) + 1;

      interface HighlightLine {
        ax: number;
        ay: number;
        bx: number;
        by: number;
        alpha: number;
      }
      const highlightedLines: HighlightLine[] = [];

      ctx.beginPath();
      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          const idx = r * cols + c;
          if (idx >= nodes.length) continue;
          const current = nodes[idx];

          // Connect Horizontal
          if (c + 1 < cols) {
            const right = nodes[r * cols + (c + 1)];
            if (right) {
              const midX = (current.x + right.x) * 0.5;
              const midY = (current.y + right.y) * 0.5;
              const mDist = mouse.isActive ? Math.hypot(midX - mouse.x, midY - mouse.y) : Infinity;

              if (mDist < 120) {
                const boost = 1 - mDist / 120;
                highlightedLines.push({
                  ax: current.x,
                  ay: current.y,
                  bx: right.x,
                  by: right.y,
                  alpha: 0.07 + boost * 0.28,
                });
              } else {
                ctx.moveTo(current.x, current.y);
                ctx.lineTo(right.x, right.y);
              }
            }
          }

          // Connect Vertical
          if (r + 1 < rows) {
            const down = nodes[(r + 1) * cols + c];
            if (down) {
              const midX = (current.x + down.x) * 0.5;
              const midY = (current.y + down.y) * 0.5;
              const mDist = mouse.isActive ? Math.hypot(midX - mouse.x, midY - mouse.y) : Infinity;

              if (mDist < 120) {
                const boost = 1 - mDist / 120;
                highlightedLines.push({
                  ax: current.x,
                  ay: current.y,
                  bx: down.x,
                  by: down.y,
                  alpha: 0.07 + boost * 0.28,
                });
              } else {
                ctx.moveTo(current.x, current.y);
                ctx.lineTo(down.x, down.y);
              }
            }
          }
        }
      }
      // Single draw call for all regular grid connection lines:
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.07)';
      ctx.lineWidth = 1;
      ctx.stroke();

      // Draw highlighted proximity lines around cursor:
      if (highlightedLines.length > 0) {
        for (let i = 0; i < highlightedLines.length; i++) {
          const hl = highlightedLines[i];
          ctx.beginPath();
          ctx.moveTo(hl.ax, hl.ay);
          ctx.lineTo(hl.bx, hl.by);
          ctx.strokeStyle = `rgba(16, 185, 129, ${hl.alpha})`;
          ctx.lineWidth = 1;
          ctx.stroke();
        }
      }

      // Draw Nodes
      ctx.beginPath();
      for (let i = 0; i < nodes.length; i++) {
        const n = nodes[i];
        if (n !== closestNode || minDistance >= mouseRadius) {
          ctx.moveTo(n.x + 1.4, n.y);
          ctx.arc(n.x, n.y, 1.4, 0, Math.PI * 2);
        }
      }
      ctx.fillStyle = 'rgba(255, 255, 255, 0.18)';
      ctx.fill();

      // Highlight active closest node
      if (closestNode && minDistance < mouseRadius) {
        ctx.beginPath();
        ctx.arc(closestNode.x, closestNode.y, 2.8, 0, Math.PI * 2);
        ctx.fillStyle = '#10b981'; // emerald-400 accent
        ctx.fill();
      }

      // Draw Radar Scanning Rings & Hex Coordinates near Active Node
      if (closestNode && minDistance < mouseRadius) {
        const activeX = closestNode.x;
        const activeY = closestNode.y;

        // Radar pulse ring 1
        ctx.beginPath();
        ctx.arc(activeX, activeY, radarPulseRadius, 0, Math.PI * 2);
        const pulseAlpha = Math.max(0, 1 - radarPulseRadius / (mouseRadius * 0.75)) * 0.35;
        ctx.strokeStyle = `rgba(16, 185, 129, ${pulseAlpha})`;
        ctx.lineWidth = 1;
        ctx.stroke();

        // Outer static boundary ring
        ctx.beginPath();
        ctx.arc(activeX, activeY, mouseRadius * 0.55, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
        ctx.setLineDash([2, 4]);
        ctx.stroke();
        ctx.setLineDash([]);

        // Hex Coordinates HUD Callout
        const labelX = activeX + 12;
        const labelY = activeY - 12;

        ctx.font = '10px "JetBrains Mono", monospace';
        ctx.fillStyle = 'rgba(16, 185, 129, 0.9)';
        ctx.fillText(`0x${closestNode.hexId}`, labelX, labelY);

        ctx.fillStyle = 'rgba(255, 255, 255, 0.45)';
        ctx.fillText(
          `${Math.round(activeX)}, ${Math.round(activeY)}`,
          labelX + 32,
          labelY
        );

        // Small indicator connector dot
        ctx.beginPath();
        ctx.arc(labelX - 4, labelY - 3, 1.2, 0, Math.PI * 2);
        ctx.fillStyle = '#10b981';
        ctx.fill();
      }

      animationFrameId = requestAnimationFrame(render);
    };

    animationFrameId = requestAnimationFrame(render);

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseleave', handleMouseLeave);
      canvas.removeEventListener('click', handleClick);
      resizeObserver.disconnect();
      intersectionObserver.disconnect();
    };
  }, [gridSpacing, mouseRadius]);

  return (
    <canvas
      ref={canvasRef}
      className={`w-full h-full block ${className}`}
      style={{ touchAction: 'none' }}
    />
  );
};
