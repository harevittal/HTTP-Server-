document.addEventListener("DOMContentLoaded", () => {
    const output = document.getElementById("api-output");

    async function testEndpoint(url, method = "GET", body = null) {
        output.textContent = `Sending ${method} ${url}...`;
        const start = performance.now();
        try {
            const options = { method };
            if (body) {
                options.headers = { "Content-Type": "application/json" };
                options.body = JSON.stringify(body);
            }
            const res = await fetch(url, options);
            const duration = (performance.now() - start).toFixed(2);
            const text = await res.text();
            
            output.textContent = `HTTP ${res.status} ${res.statusText} (${duration} ms)\nHeaders:\n` +
                Array.from(res.headers.entries()).map(([k, v]) => `  ${k}: ${v}`).join("\n") +
                `\n\nBody:\n${text}`;
        } catch (err) {
            output.textContent = `Error: ${err.message}`;
        }
    }

    document.getElementById("btn-health")?.addEventListener("click", () => {
        testEndpoint("/api/health");
    });

    document.getElementById("btn-time")?.addEventListener("click", () => {
        testEndpoint("/api/time");
    });

    document.getElementById("btn-post")?.addEventListener("click", () => {
        testEndpoint("/api/echo", "POST", {
            message: "Hello from Pure Python Non-blocking Server!",
            timestamp: Date.now()
        });
    });
});
