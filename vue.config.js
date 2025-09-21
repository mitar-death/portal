const { defineConfig } = require('@vue/cli-service')

const backendUrl = process.env.BACKEND_URL
module.exports = defineConfig({
  transpileDependencies: true,

  // Temporarily disable eslint during development
  lintOnSave: false,

  // Configure proxy for API requests
  devServer: {
    port: 5000,
    host: '0.0.0.0',
    allowedHosts: 'all',
    proxy: {
      '/api': {
        target: "http://localhost:8030", // Use the backend URL from .env
        changeOrigin: true,
        // Don't rewrite the path since our API already expects /api prefix
        pathRewrite: null
      }
    }
  },

  configureWebpack: {
    resolve: {
      fallback: {
        fs: false,
        util: require.resolve('util/'),
        assert: require.resolve('assert/'),
        stream: require.resolve('stream-browserify'),
      },
    },
  },
})
