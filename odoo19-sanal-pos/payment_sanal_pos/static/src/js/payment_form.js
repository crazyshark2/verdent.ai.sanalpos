/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";
import { BinDetector } from "./bin_detector";

/**
 * SanalPosPaymentForm - Ödeme sayfası ana kart formu.
 *
 * Odoo ödeme formunu extend ederek:
 * - BIN algılama
 * - Taksit seçimi
 * - 3D Secure form gönderimi
 * özelliklerini ekler.
 */
export class SanalPosPaymentForm extends Component {
    static template = 'payment_sanal_pos.PaymentForm';
    static props = {
        amount: { type: Number },
        providerId: { type: Number },
        providerCode: { type: String },
        reference: { type: String, optional: true },
    };

    setup() {
        this.binDetector = new BinDetector();
        this.state = useState({
            cardNumber: '',
            cardHolder: '',
            expMonth: '',
            expYear: '',
            cvv: '',
            bankInfo: null,
            cardNetworkIcon: 'fa fa-credit-card',
            installments: [],
            selectedInstallment: 1,
            loading: false,
            error: null,
        });
    }

    /**
     * Kart numarası değiştiğinde.
     * @param {Event} ev
     */
    onCardNumberInput(ev) {
        const raw = ev.target.value;
        const formatted = BinDetector.formatCardNumber(raw);
        this.state.cardNumber = formatted;
        ev.target.value = formatted;

        // BIN algılama
        const cleaned = raw.replace(/\D/g, '');
        this.binDetector.detectDebounced(cleaned, (result) => {
            if (result && result.bank_code) {
                this.state.bankInfo = result;
                this.state.cardNetworkIcon = BinDetector.getNetworkIcon(
                    result.card_network
                );
                this._fetchInstallments(cleaned.substring(0, 6));
            } else if (cleaned.length < 6) {
                this.state.bankInfo = null;
                this.state.cardNetworkIcon = 'fa fa-credit-card';
                this.state.installments = [];
            }
        });
    }

    /**
     * Taksit seçeneklerini getir.
     * @param {string} bin
     */
    async _fetchInstallments(bin) {
        try {
            const response = await fetch('/sanal_pos/installments/by_bin', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    params: {
                        bin_number: bin,
                        amount: this.props.amount,
                    },
                }),
            });
            const data = await response.json();
            const result = data.result || {};
            this.state.installments = result.installments || [];
        } catch (e) {
            console.warn('Installment fetch error:', e);
        }
    }

    /**
     * Taksit seçimi.
     * @param {number} count
     */
    selectInstallment(count) {
        this.state.selectedInstallment = count;
    }

    /**
     * Form gönderimi.
     * Kart bilgilerini render values'a ekleyerek
     * 3D Secure yönlendirmesini başlatır.
     */
    async onSubmit() {
        this.state.error = null;

        // Validasyon
        const cardClean = this.state.cardNumber.replace(/\s/g, '');
        if (cardClean.length < 15) {
            this.state.error = 'Geçerli bir kart numarası girin';
            return;
        }
        if (!this.state.expMonth || !this.state.expYear) {
            this.state.error = 'Son kullanma tarihini girin';
            return;
        }
        if (!this.state.cvv || this.state.cvv.length < 3) {
            this.state.error = 'CVV kodunu girin';
            return;
        }

        this.state.loading = true;

        try {
            // Kart verilerini ödeme formuna ekle
            const cardData = {
                number: cardClean,
                holder: this.state.cardHolder,
                exp_month: this.state.expMonth.padStart(2, '0'),
                exp_year: this.state.expYear,
                cvv: this.state.cvv,
            };

            // Odoo payment form submit (3D redirect yapılacak)
            const form = document.querySelector('form[name="o_payment_checkout"]');
            if (form) {
                // Hidden input'lara kart verisi ekle
                this._addHiddenInput(form, 'sanal_pos_card_number', cardClean);
                this._addHiddenInput(form, 'sanal_pos_card_holder', this.state.cardHolder);
                this._addHiddenInput(form, 'sanal_pos_exp_month', cardData.exp_month);
                this._addHiddenInput(form, 'sanal_pos_exp_year', cardData.exp_year);
                this._addHiddenInput(form, 'sanal_pos_cvv', this.state.cvv);
                this._addHiddenInput(
                    form, 'sanal_pos_installment',
                    String(this.state.selectedInstallment)
                );
                form.submit();
            }
        } catch (e) {
            console.error('Payment submit error:', e);
            this.state.error = 'Ödeme işlemi başlatılamadı: ' + e.message;
        } finally {
            this.state.loading = false;
        }
    }

    /**
     * Forma hidden input ekle.
     * @param {HTMLFormElement} form
     * @param {string} name
     * @param {string} value
     */
    _addHiddenInput(form, name, value) {
        let input = form.querySelector(`input[name="${name}"]`);
        if (!input) {
            input = document.createElement('input');
            input.type = 'hidden';
            input.name = name;
            form.appendChild(input);
        }
        input.value = value;
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
