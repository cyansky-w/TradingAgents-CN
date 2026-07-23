// vite.config.ts
import { defineConfig } from "file:///D:/1workplace/project/TradingAgents-CN/frontend/node_modules/vitest/dist/config.js";
import vue from "file:///D:/1workplace/project/TradingAgents-CN/frontend/node_modules/@vitejs/plugin-vue/dist/index.mjs";
import { resolve } from "path";
import AutoImport from "file:///D:/1workplace/project/TradingAgents-CN/frontend/node_modules/unplugin-auto-import/dist/vite.js";
import Components from "file:///D:/1workplace/project/TradingAgents-CN/frontend/node_modules/unplugin-vue-components/dist/vite.js";
import { ElementPlusResolver } from "file:///D:/1workplace/project/TradingAgents-CN/frontend/node_modules/unplugin-vue-components/dist/resolvers.js";
var __vite_injected_original_dirname = "D:\\1workplace\\project\\TradingAgents-CN\\.worktrees\\real-portfolio-crypto\\frontend";
var vite_config_default = defineConfig({
  test: {
    environment: "jsdom",
    globals: true,
    include: ["src/**/*.test.ts"]
  },
  plugins: [
    vue(),
    AutoImport({
      resolvers: [ElementPlusResolver()],
      imports: [
        "vue",
        "vue-router",
        "pinia",
        "@vueuse/core"
      ],
      dts: true,
      eslintrc: {
        enabled: true
      }
    }),
    // 自动按需组件导入
    Components({
      resolvers: [ElementPlusResolver()],
      dts: true
    })
  ],
  resolve: {
    alias: {
      "@": resolve(__vite_injected_original_dirname, "src"),
      "@components": resolve(__vite_injected_original_dirname, "src/components"),
      "@views": resolve(__vite_injected_original_dirname, "src/views"),
      "@stores": resolve(__vite_injected_original_dirname, "src/stores"),
      "@utils": resolve(__vite_injected_original_dirname, "src/utils"),
      "@types": resolve(__vite_injected_original_dirname, "src/types"),
      "@api": resolve(__vite_injected_original_dirname, "src/api")
    }
  },
  server: {
    host: "0.0.0.0",
    port: 3e3,
    hmr: {
      overlay: false
    },
    // 允许从项目根目录之外（例如 /docs）导入原始文件
    fs: {
      allow: [resolve(__vite_injected_original_dirname, "..")]
    },
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        secure: false,
        ws: true
        // 🔥 启用 WebSocket 代理支持
      }
    }
  },
  build: {
    target: "es2020",
    // 支持 nullish coalescing operator (??) 和 optional chaining (?.)
    outDir: "dist",
    assetsDir: "assets",
    sourcemap: false,
    rollupOptions: {
      output: {
        chunkFileNames: "js/[name]-[hash].js",
        entryFileNames: "js/[name]-[hash].js",
        assetFileNames: "[ext]/[name]-[hash].[ext]"
      }
    }
  },
  css: {
    preprocessorOptions: {
      scss: {
        additionalData: `@use "@/styles/variables.scss" as *;`
      }
    }
  }
});
export {
  vite_config_default as default
};
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsidml0ZS5jb25maWcudHMiXSwKICAic291cmNlc0NvbnRlbnQiOiBbImNvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9kaXJuYW1lID0gXCJEOlxcXFwxd29ya3BsYWNlXFxcXHByb2plY3RcXFxcVHJhZGluZ0FnZW50cy1DTlxcXFwud29ya3RyZWVzXFxcXHJlYWwtcG9ydGZvbGlvLWNyeXB0b1xcXFxmcm9udGVuZFwiO2NvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9maWxlbmFtZSA9IFwiRDpcXFxcMXdvcmtwbGFjZVxcXFxwcm9qZWN0XFxcXFRyYWRpbmdBZ2VudHMtQ05cXFxcLndvcmt0cmVlc1xcXFxyZWFsLXBvcnRmb2xpby1jcnlwdG9cXFxcZnJvbnRlbmRcXFxcdml0ZS5jb25maWcudHNcIjtjb25zdCBfX3ZpdGVfaW5qZWN0ZWRfb3JpZ2luYWxfaW1wb3J0X21ldGFfdXJsID0gXCJmaWxlOi8vL0Q6LzF3b3JrcGxhY2UvcHJvamVjdC9UcmFkaW5nQWdlbnRzLUNOLy53b3JrdHJlZXMvcmVhbC1wb3J0Zm9saW8tY3J5cHRvL2Zyb250ZW5kL3ZpdGUuY29uZmlnLnRzXCI7aW1wb3J0IHsgZGVmaW5lQ29uZmlnIH0gZnJvbSAndml0ZXN0L2NvbmZpZydcbmltcG9ydCB2dWUgZnJvbSAnQHZpdGVqcy9wbHVnaW4tdnVlJ1xuaW1wb3J0IHsgcmVzb2x2ZSB9IGZyb20gJ3BhdGgnXG5pbXBvcnQgQXV0b0ltcG9ydCBmcm9tICd1bnBsdWdpbi1hdXRvLWltcG9ydC92aXRlJ1xuaW1wb3J0IENvbXBvbmVudHMgZnJvbSAndW5wbHVnaW4tdnVlLWNvbXBvbmVudHMvdml0ZSdcbmltcG9ydCB7IEVsZW1lbnRQbHVzUmVzb2x2ZXIgfSBmcm9tICd1bnBsdWdpbi12dWUtY29tcG9uZW50cy9yZXNvbHZlcnMnXG5cbi8vIGh0dHBzOi8vdml0ZWpzLmRldi9jb25maWcvXG5leHBvcnQgZGVmYXVsdCBkZWZpbmVDb25maWcoe1xuICB0ZXN0OiB7XG4gICAgZW52aXJvbm1lbnQ6ICdqc2RvbScsXG4gICAgZ2xvYmFsczogdHJ1ZSxcbiAgICBpbmNsdWRlOiBbJ3NyYy8qKi8qLnRlc3QudHMnXVxuICB9LFxuICBwbHVnaW5zOiBbXG4gICAgdnVlKCksXG4gICAgQXV0b0ltcG9ydCh7XG4gICAgICByZXNvbHZlcnM6IFtFbGVtZW50UGx1c1Jlc29sdmVyKCldLFxuICAgICAgaW1wb3J0czogW1xuICAgICAgICAndnVlJyxcbiAgICAgICAgJ3Z1ZS1yb3V0ZXInLFxuICAgICAgICAncGluaWEnLFxuICAgICAgICAnQHZ1ZXVzZS9jb3JlJ1xuICAgICAgXSxcbiAgICAgIGR0czogdHJ1ZSxcbiAgICAgIGVzbGludHJjOiB7XG4gICAgICAgIGVuYWJsZWQ6IHRydWVcbiAgICAgIH1cbiAgICB9KSxcbiAgICAvLyBcdTgxRUFcdTUyQThcdTYzMDlcdTk3MDBcdTdFQzRcdTRFRjZcdTVCRkNcdTUxNjVcbiAgICBDb21wb25lbnRzKHtcbiAgICAgIHJlc29sdmVyczogW0VsZW1lbnRQbHVzUmVzb2x2ZXIoKV0sXG4gICAgICBkdHM6IHRydWVcbiAgICB9KVxuICBdLFxuICByZXNvbHZlOiB7XG4gICAgYWxpYXM6IHtcbiAgICAgICdAJzogcmVzb2x2ZShfX2Rpcm5hbWUsICdzcmMnKSxcbiAgICAgICdAY29tcG9uZW50cyc6IHJlc29sdmUoX19kaXJuYW1lLCAnc3JjL2NvbXBvbmVudHMnKSxcbiAgICAgICdAdmlld3MnOiByZXNvbHZlKF9fZGlybmFtZSwgJ3NyYy92aWV3cycpLFxuICAgICAgJ0BzdG9yZXMnOiByZXNvbHZlKF9fZGlybmFtZSwgJ3NyYy9zdG9yZXMnKSxcbiAgICAgICdAdXRpbHMnOiByZXNvbHZlKF9fZGlybmFtZSwgJ3NyYy91dGlscycpLFxuICAgICAgJ0B0eXBlcyc6IHJlc29sdmUoX19kaXJuYW1lLCAnc3JjL3R5cGVzJyksXG4gICAgICAnQGFwaSc6IHJlc29sdmUoX19kaXJuYW1lLCAnc3JjL2FwaScpXG4gICAgfVxuICB9LFxuICBzZXJ2ZXI6IHtcbiAgICBob3N0OiAnMC4wLjAuMCcsXG4gICAgcG9ydDogMzAwMCxcbiAgICBobXI6IHtcbiAgICAgIG92ZXJsYXk6IGZhbHNlXG4gICAgfSxcbiAgICAvLyBcdTUxNDFcdThCQjhcdTRFQ0VcdTk4NzlcdTc2RUVcdTY4MzlcdTc2RUVcdTVGNTVcdTRFNEJcdTU5MTZcdUZGMDhcdTRGOEJcdTU5ODIgL2RvY3NcdUZGMDlcdTVCRkNcdTUxNjVcdTUzOUZcdTU5Q0JcdTY1ODdcdTRFRjZcbiAgICBmczoge1xuICAgICAgYWxsb3c6IFtyZXNvbHZlKF9fZGlybmFtZSwgJy4uJyldXG4gICAgfSxcbiAgICBwcm94eToge1xuICAgICAgJy9hcGknOiB7XG4gICAgICAgIHRhcmdldDogJ2h0dHA6Ly9sb2NhbGhvc3Q6ODAwMCcsXG4gICAgICAgIGNoYW5nZU9yaWdpbjogdHJ1ZSxcbiAgICAgICAgc2VjdXJlOiBmYWxzZSxcbiAgICAgICAgd3M6IHRydWUgIC8vIFx1RDgzRFx1REQyNSBcdTU0MkZcdTc1MjggV2ViU29ja2V0IFx1NEVFM1x1NzQwNlx1NjUyRlx1NjMwMVxuICAgICAgfVxuICAgIH1cbiAgfSxcbiAgYnVpbGQ6IHtcbiAgICB0YXJnZXQ6ICdlczIwMjAnLCAgLy8gXHU2NTJGXHU2MzAxIG51bGxpc2ggY29hbGVzY2luZyBvcGVyYXRvciAoPz8pIFx1NTQ4QyBvcHRpb25hbCBjaGFpbmluZyAoPy4pXG4gICAgb3V0RGlyOiAnZGlzdCcsXG4gICAgYXNzZXRzRGlyOiAnYXNzZXRzJyxcbiAgICBzb3VyY2VtYXA6IGZhbHNlLFxuICAgIHJvbGx1cE9wdGlvbnM6IHtcbiAgICAgIG91dHB1dDoge1xuICAgICAgICBjaHVua0ZpbGVOYW1lczogJ2pzL1tuYW1lXS1baGFzaF0uanMnLFxuICAgICAgICBlbnRyeUZpbGVOYW1lczogJ2pzL1tuYW1lXS1baGFzaF0uanMnLFxuICAgICAgICBhc3NldEZpbGVOYW1lczogJ1tleHRdL1tuYW1lXS1baGFzaF0uW2V4dF0nXG4gICAgICB9XG4gICAgfVxuICB9LFxuICBjc3M6IHtcbiAgICBwcmVwcm9jZXNzb3JPcHRpb25zOiB7XG4gICAgICBzY3NzOiB7XG4gICAgICAgIGFkZGl0aW9uYWxEYXRhOiBgQHVzZSBcIkAvc3R5bGVzL3ZhcmlhYmxlcy5zY3NzXCIgYXMgKjtgXG4gICAgICB9XG4gICAgfVxuICB9XG59KVxuIl0sCiAgIm1hcHBpbmdzIjogIjtBQUFnYixTQUFTLG9CQUFvQjtBQUM3YyxPQUFPLFNBQVM7QUFDaEIsU0FBUyxlQUFlO0FBQ3hCLE9BQU8sZ0JBQWdCO0FBQ3ZCLE9BQU8sZ0JBQWdCO0FBQ3ZCLFNBQVMsMkJBQTJCO0FBTHBDLElBQU0sbUNBQW1DO0FBUXpDLElBQU8sc0JBQVEsYUFBYTtBQUFBLEVBQzFCLE1BQU07QUFBQSxJQUNKLGFBQWE7QUFBQSxJQUNiLFNBQVM7QUFBQSxJQUNULFNBQVMsQ0FBQyxrQkFBa0I7QUFBQSxFQUM5QjtBQUFBLEVBQ0EsU0FBUztBQUFBLElBQ1AsSUFBSTtBQUFBLElBQ0osV0FBVztBQUFBLE1BQ1QsV0FBVyxDQUFDLG9CQUFvQixDQUFDO0FBQUEsTUFDakMsU0FBUztBQUFBLFFBQ1A7QUFBQSxRQUNBO0FBQUEsUUFDQTtBQUFBLFFBQ0E7QUFBQSxNQUNGO0FBQUEsTUFDQSxLQUFLO0FBQUEsTUFDTCxVQUFVO0FBQUEsUUFDUixTQUFTO0FBQUEsTUFDWDtBQUFBLElBQ0YsQ0FBQztBQUFBO0FBQUEsSUFFRCxXQUFXO0FBQUEsTUFDVCxXQUFXLENBQUMsb0JBQW9CLENBQUM7QUFBQSxNQUNqQyxLQUFLO0FBQUEsSUFDUCxDQUFDO0FBQUEsRUFDSDtBQUFBLEVBQ0EsU0FBUztBQUFBLElBQ1AsT0FBTztBQUFBLE1BQ0wsS0FBSyxRQUFRLGtDQUFXLEtBQUs7QUFBQSxNQUM3QixlQUFlLFFBQVEsa0NBQVcsZ0JBQWdCO0FBQUEsTUFDbEQsVUFBVSxRQUFRLGtDQUFXLFdBQVc7QUFBQSxNQUN4QyxXQUFXLFFBQVEsa0NBQVcsWUFBWTtBQUFBLE1BQzFDLFVBQVUsUUFBUSxrQ0FBVyxXQUFXO0FBQUEsTUFDeEMsVUFBVSxRQUFRLGtDQUFXLFdBQVc7QUFBQSxNQUN4QyxRQUFRLFFBQVEsa0NBQVcsU0FBUztBQUFBLElBQ3RDO0FBQUEsRUFDRjtBQUFBLEVBQ0EsUUFBUTtBQUFBLElBQ04sTUFBTTtBQUFBLElBQ04sTUFBTTtBQUFBLElBQ04sS0FBSztBQUFBLE1BQ0gsU0FBUztBQUFBLElBQ1g7QUFBQTtBQUFBLElBRUEsSUFBSTtBQUFBLE1BQ0YsT0FBTyxDQUFDLFFBQVEsa0NBQVcsSUFBSSxDQUFDO0FBQUEsSUFDbEM7QUFBQSxJQUNBLE9BQU87QUFBQSxNQUNMLFFBQVE7QUFBQSxRQUNOLFFBQVE7QUFBQSxRQUNSLGNBQWM7QUFBQSxRQUNkLFFBQVE7QUFBQSxRQUNSLElBQUk7QUFBQTtBQUFBLE1BQ047QUFBQSxJQUNGO0FBQUEsRUFDRjtBQUFBLEVBQ0EsT0FBTztBQUFBLElBQ0wsUUFBUTtBQUFBO0FBQUEsSUFDUixRQUFRO0FBQUEsSUFDUixXQUFXO0FBQUEsSUFDWCxXQUFXO0FBQUEsSUFDWCxlQUFlO0FBQUEsTUFDYixRQUFRO0FBQUEsUUFDTixnQkFBZ0I7QUFBQSxRQUNoQixnQkFBZ0I7QUFBQSxRQUNoQixnQkFBZ0I7QUFBQSxNQUNsQjtBQUFBLElBQ0Y7QUFBQSxFQUNGO0FBQUEsRUFDQSxLQUFLO0FBQUEsSUFDSCxxQkFBcUI7QUFBQSxNQUNuQixNQUFNO0FBQUEsUUFDSixnQkFBZ0I7QUFBQSxNQUNsQjtBQUFBLElBQ0Y7QUFBQSxFQUNGO0FBQ0YsQ0FBQzsiLAogICJuYW1lcyI6IFtdCn0K
