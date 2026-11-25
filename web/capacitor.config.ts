import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "com.infinitosoft.mara",
  appName: "Mara DBV",
  webDir: "out",
  server: {
    // Em publicação nativa nas lojas (Google Play / App Store), aponte para a API oficial:
    // url: "https://mara.infinitosoft.com",
    androidScheme: "https",
  },
  plugins: {
    SplashScreen: {
      launchShowDuration: 1200,
      backgroundColor: "#010440",
      showSpinner: false,
    },
  },
};

export default config;
