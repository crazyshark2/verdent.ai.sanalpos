/** @odoo-module **/

/**
 * BIN Detector - Kart numarası BIN tanıma modülü.
 *
 * Kart numarasının ilk 6 hanesi girildiğinde
 * sunucuya BIN sorgulama isteği gönderir ve
 * banka bilgisini döndürür.
 */
export class BinDetector {
    constructor() {
        this._cache = new Map();
        this._debounceTimer = null;
        this._debounceMs = 300;
    }

    /**
     * BIN numarasını algıla ve banka bilgisini döndür.
     * @param {string} cardNumber - Kart numarası (en az 6 hane)
     * @returns {Promise<Object>} Banka bilgisi
     */
    async detect(cardNumber) {
        const cleaned = cardNumber.replace(/\s+/g, '').replace(/-/g, '');
        if (cleaned.length < 6) {
            return null;
        }
        const bin = cleaned.substring(0, 6);

        // Cache kontrolü
        if (this._cache.has(bin)) {
            return this._cache.get(bin);
        }

        try {
            const result = await this._fetchBinInfo(bin);
            if (result && result.bank_code) {
                this._cache.set(bin, result);
            }
            return result;
        } catch (e) {
            console.warn('BIN detection failed:', e);
            return null;
        }
    }

    /**
     * BIN bilgisini sunucudan sorgula.
     * @param {string} bin - İlk 6 hane
     * @returns {Promise<Object>}
     */
    async _fetchBinInfo(bin) {
        const response = await fetch('/sanal_pos/bin/detect', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                jsonrpc: '2.0',
                method: 'call',
                params: { bin_number: bin },
            }),
        });
        const data = await response.json();
        return data.result || {};
    }

    /**
     * Debounce'lu BIN algılama.
     * @param {string} cardNumber
     * @param {Function} callback
     */
    detectDebounced(cardNumber, callback) {
        if (this._debounceTimer) {
            clearTimeout(this._debounceTimer);
        }
        this._debounceTimer = setTimeout(async () => {
            const result = await this.detect(cardNumber);
            callback(result);
        }, this._debounceMs);
    }

    /**
     * Kart ağını ikon olarak döndür.
     * @param {string} network - visa, mastercard, troy, amex
     * @returns {string} Ikon CSS sınıfı
     */
    static getNetworkIcon(network) {
        const icons = {
            visa: 'fa fa-cc-visa',
            mastercard: 'fa fa-cc-mastercard',
            amex: 'fa fa-cc-amex',
            troy: 'fa fa-credit-card',
        };
        return icons[network] || 'fa fa-credit-card';
    }

    /**
     * Kart numarasını formatla (4'lü gruplar).
     * @param {string} value
     * @returns {string}
     */
    static formatCardNumber(value) {
        const cleaned = value.replace(/\D/g, '');
        const groups = [];
        for (let i = 0; i < cleaned.length && i < 16; i += 4) {
            groups.push(cleaned.substring(i, i + 4));
        }
        return groups.join(' ');
    }
}
