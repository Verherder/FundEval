export function createPerformanceCrosshairPlugin() {
    return {
        id: 'fundPerformanceCrosshairPlugin',
        afterEvent(chart, args) {
            const event = args.event;
            if (!event || event.type === 'mouseout') {
                chart.$fundPerformanceCrosshair = null;
                args.changed = true;
                return;
            }

            const {left, right, top, bottom} = chart.chartArea;
            if (event.x < left || event.x > right || event.y < top || event.y > bottom) {
                chart.$fundPerformanceCrosshair = null;
                args.changed = true;
                return;
            }

            chart.$fundPerformanceCrosshair = {x: event.x, y: event.y};
            args.changed = true;
        },
        afterDatasetsDraw(chart) {
            if (!chart.$fundPerformanceCrosshair) return;
            const {x, y} = chart.$fundPerformanceCrosshair;
            const {left, right, top, bottom} = chart.chartArea;
            const ctx = chart.ctx;
            ctx.save();
            ctx.beginPath();
            ctx.setLineDash([5, 4]);
            ctx.lineWidth = 1;
            ctx.strokeStyle = 'rgba(148, 163, 184, 0.85)';
            ctx.moveTo(x, top);
            ctx.lineTo(x, bottom);
            ctx.moveTo(left, y);
            ctx.lineTo(right, y);
            ctx.stroke();
            ctx.restore();
        }
    };
}
