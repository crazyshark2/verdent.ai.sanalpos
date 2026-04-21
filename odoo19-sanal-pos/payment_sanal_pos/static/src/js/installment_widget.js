/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

/**
 * InstallmentWidget - Ürün sayfasında taksit tablosu widget'ı.
 *
 * Ürünün fiyatına göre tüm aktif bankalardan taksit
 * hesaplaması yaparak tablo olarak gösterir.
 */
export class InstallmentWidget extends Component {
    static template = 'payment_sanal_pos.InstallmentWidget';
    static props = {
        productId: { type: Number },
    };

    setup() {
        this.state = useState({
            loading: true,
            productPrice: 0,
            banks: [],
            selectedBank: null,
            error: null,
        });

        onMounted(() => {
            this.fetchInstallments();
        });
    }

    /**
     * Ürün için tüm banka taksit seçeneklerini getir.
     */
    async fetchInstallments() {
        this.state.loading = true;

        try {
            const response = await fetch('/sanal_pos/installments/by_product', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    params: {
                        product_id: this.props.productId,
                    },
                }),
            });
            const data = await response.json();
            const result = data.result || {};

            this.state.productPrice = result.product_price || 0;
            this.state.banks = result.banks || [];

            if (this.state.banks.length > 0) {
                this.state.selectedBank = this.state.banks[0].code;
            }
        } catch (e) {
            console.error('Installment widget error:', e);
            this.state.error = 'Taksit bilgisi alınamadı';
        } finally {
            this.state.loading = false;
        }
    }

    /**
     * Banka seçimini değiştir.
     * @param {string} bankCode
     */
    selectBank(bankCode) {
        this.state.selectedBank = bankCode;
    }

    /**
     * Seçili banka bilgisini döndür.
     * @returns {Object|null}
     */
    get selectedBankData() {
        if (!this.state.selectedBank) return null;
        return this.state.banks.find(b => b.code === this.state.selectedBank);
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
