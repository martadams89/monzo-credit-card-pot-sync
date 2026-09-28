// Passkey (WebAuthn) helpers: convert the server's JSON options to what the
// browser API takes, and the browser's credential back to JSON.
(function () {
    function toBuffer(value) {
        const base64 = value.replace(/-/g, "+").replace(/_/g, "/");
        const padded = base64 + "===".slice((base64.length + 3) % 4);
        return Uint8Array.from(atob(padded), c => c.charCodeAt(0)).buffer;
    }

    function toBase64url(buffer) {
        let binary = "";
        new Uint8Array(buffer).forEach(b => { binary += String.fromCharCode(b); });
        return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
    }

    function credentialToJSON(credential) {
        const response = credential.response;
        const json = {
            id: credential.id,
            rawId: toBase64url(credential.rawId),
            type: credential.type,
            clientExtensionResults: credential.getClientExtensionResults ? credential.getClientExtensionResults() : {},
            response: { clientDataJSON: toBase64url(response.clientDataJSON) },
        };
        if (response.attestationObject) {
            json.response.attestationObject = toBase64url(response.attestationObject);
            if (response.getTransports) json.response.transports = response.getTransports();
        }
        if (response.authenticatorData) {
            json.response.authenticatorData = toBase64url(response.authenticatorData);
            json.response.signature = toBase64url(response.signature);
            if (response.userHandle) json.response.userHandle = toBase64url(response.userHandle);
        }
        if (credential.authenticatorAttachment) json.authenticatorAttachment = credential.authenticatorAttachment;
        return json;
    }

    async function postJSON(url, body) {
        const response = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json", "Accept": "application/json" },
            body: JSON.stringify(body || {}),
            credentials: "same-origin",
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.error || "Something went wrong");
        return data;
    }

    function supported() {
        return window.isSecureContext && !!window.PublicKeyCredential;
    }

    async function register(optionsUrl, saveUrl, name) {
        const options = await postJSON(optionsUrl);
        options.challenge = toBuffer(options.challenge);
        options.user.id = toBuffer(options.user.id);
        (options.excludeCredentials || []).forEach(c => { c.id = toBuffer(c.id); });
        const credential = await navigator.credentials.create({ publicKey: options });
        return postJSON(saveUrl, { name: name, credential: credentialToJSON(credential) });
    }

    async function signIn(optionsUrl, verifyUrl) {
        const options = await postJSON(optionsUrl);
        options.challenge = toBuffer(options.challenge);
        (options.allowCredentials || []).forEach(c => { c.id = toBuffer(c.id); });
        const credential = await navigator.credentials.get({ publicKey: options });
        return postJSON(verifyUrl, credentialToJSON(credential));
    }

    window.Passkeys = { supported, register, signIn };
})();
