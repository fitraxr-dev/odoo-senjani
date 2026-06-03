import { patch } from "@web/core/utils/patch";
import { JournalDashboardGraphField } from "@web/views/fields/journal_dashboard_graph/journal_dashboard_graph_field";

patch(JournalDashboardGraphField.prototype, {
    getLineChartConfig() {
        const config = super.getLineChartConfig(...arguments);
        const values = this.data[0].values || [];
        const allZero = values.every(v => v.y === 0);
        if (allZero) {
            if (!config.options.scales.y) {
                config.options.scales.y = {};
            }
            config.options.scales.y.min = 0;
            config.options.scales.y.suggestedMax = 1;
        }
        return config;
    }
});
