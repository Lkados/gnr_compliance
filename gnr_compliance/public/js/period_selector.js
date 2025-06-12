// public/js/period_selector.js
frappe.ui.form.ControlGNRPeriodSelector = class extends frappe.ui.form.ControlData {
    make_input() {
        super.make_input();
        this.setup_period_selector();
    }
    
    setup_period_selector() {
        const $wrapper = $('<div class="gnr-period-selector"></div>');
        
        // Sélection rapide de période
        const quick_periods = [
            {label: 'T1 Actuel', value: 'current_q1'},
            {label: 'T2 Actuel', value: 'current_q2'},
            {label: 'T3 Actuel', value: 'current_q3'},
            {label: 'T4 Actuel', value: 'current_q4'},
            {label: 'Semestre 1', value: 'semester_1'},
            {label: 'Semestre 2', value: 'semester_2'}
        ];
        
        quick_periods.forEach(period => {
            const $btn = $(`<button class="btn btn-sm btn-default" 
                            data-period="${period.value}">${period.label}</button>`);
            $wrapper.append($btn);
        });
        
        this.$input.after($wrapper);
        this.bind_period_events();
    }
    
    bind_period_events() {
        const me = this;
        this.$wrapper.find('[data-period]').on('click', function() {
            const period = $(this).data('period');
            const dates = me.get_period_dates(period);
            me.frm.set_value('from_date', dates.from_date);
            me.frm.set_value('to_date', dates.to_date);
        });
    }
    
    get_period_dates(period) {
        const year = new Date().getFullYear();
        const periods = {
            'current_q1': {from_date: `${year}-01-01`, to_date: `${year}-03-31`},
            'current_q2': {from_date: `${year}-04-01`, to_date: `${year}-06-30`},
            'current_q3': {from_date: `${year}-07-01`, to_date: `${year}-09-30`},
            'current_q4': {from_date: `${year}-10-01`, to_date: `${year}-12-31`},
            'semester_1': {from_date: `${year}-01-01`, to_date: `${year}-06-30`},
            'semester_2': {from_date: `${year}-07-01`, to_date: `${year}-12-31`}
        };
        return periods[period];
    }
};