/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";

/**
 * InstallmentSelector - Ödeme sayfasında taksit seçimi bileşeni.
 *
 * BIN algılandığında taksit seçeneklerini sunucudan alır ve
 * kullanıcıya gösterir.
 */
export class InstallmentSelector extends Component {
    static template = 'payment_sanal_pos.InstallmentSelector';
    static props = {
        amount: { type: Number },
        binNumber: { type: String, optional: true },
        onSelect: { type: Function },
    };

    setup() {
        this.state = useState({
            loading: false,
            bankInfo: null,
            installments: [],
            selectedInstallment: 1,
            error: null,
        });

        onMounted(() => {
            if (this.props.binNumber && this.props.binNumber.length >= 6) {
                this.fetchInstallments(this.props.binNumber);
            }
        });
    }

    /**
     * BIN'e göre taksit seçeneklerini getir.
     * @param {string} binNumber
     */
    async fetchInstallments(binNumber) {
        if (!binNumber || binNumber.length < 6) {
            this.state.installments = [];
            this.state.bankInfo = null;
            return;
        }

        this.state.loading = true;
        this.state.error = null;

        try {
            const response = await fetch('/sanal_pos/installments/by_bin', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    params: {
                        bin_number: binNumber.substring(0, 6),
                        amount: this.props.amount,
                    },
                }),
            });
            const data = await response.json();
            const result = data.result || {};

            this.state.bankInfo = result.bank || null;
            this.state.installments = result.installments || [];

            if (this.state.installments.length > 0) {
                this.state.selectedInstallment = this.state.installments[0].count;
            }
        } catch (e) {
            console.error('Installment fetch error:', e);
            this.state.error = 'Taksit bilgisi alınamadı';
        } finally {
            this.state.loading = false;
        }
    }

    /**
     * Taksit seçimini güncelle.
     * @param {number} count - Taksit sayısı
     */
    selectInstallment(count) {
        this.state.selectedInstallment = count;
        const selected = this.state.installments.find(i => i.count === count);
        if (this.props.onSelect && selected) {
            this.props.onSelect({
                count: selected.count,
                monthly: selected.monthly,
                total: selected.total,
                rate: selected.rate,
            });
        }
    }

    /**
     * Para formatla.
     * @param {number} value
     * @returns {string}
     */
    formatCurrency(value) {
        return new Intl.NumberFormat('tr-TR', {
            style: 'currency',
            currency: 'TRY',
        }).format(value);
    }
}
