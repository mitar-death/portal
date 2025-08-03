const functions = require("firebase-functions");
const express = require("express");
const { createProxyMiddleware } = require("http-proxy-middleware");

const app = express();

// Backend target, configurable via Firebase config
const TARGET = (functions.config().backend && functions.config().backend.url) || "https://api.yourdomain.com";

app.use(
    "/api",
    createProxyMiddleware({
        target: TARGET,
        changeOrigin: true,
        secure: true,
        pathRewrite: {
            "^/api": "/api" // adjust if your backend expects a different base path
        },
        onError: (err, req, res) => {
            console.error("Proxy error:", err);
            res.status(502).send("Bad Gateway");
        },
        onProxyReq: (proxyReq, req) => {
            // Optionally forward auth headers, etc.
            if (req.headers.authorization) {
                proxyReq.setHeader("authorization", req.headers.authorization);
            }
            proxyReq.setHeader("x-forwarded-for", req.ip);
        },
        timeout: 10000,
        proxyTimeout: 10000
    })
);

// Health check or root
app.get("/", (req, res) => res.send("API proxy is running"));

exports.api = functions.https.onRequest(app);
