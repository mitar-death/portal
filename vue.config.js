const { defineConfig } = require('@vue/cli-service')

const backendUrl = process.env.BACKEND_URL
module.exports = defineConfig({
  transpileDependencies: true,

  // Temporarily disable eslint during development
  lintOnSave: false,

  // Configure proxy for API requests
  devServer: {
    port: 8080,
    proxy: {
      '/api': {
        target: "http://127.0.0.1:8030", // Use the backend URL from .env
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
