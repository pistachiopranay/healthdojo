// @ts-check
import { defineConfig, fontProviders } from "astro/config";
import starlight from "@astrojs/starlight";
import starlightThemeBlack from "starlight-theme-black";

const NAV = [
  { label: "Overview", link: "/" },
  { label: "Results", link: "/results/" },
  { label: "Method", link: "/method/" },
  { label: "Explore", link: "/explore/" },
];

export default defineConfig({
  site: "https://healthdojo.dev",
  trailingSlash: "ignore",
  build: { format: "directory" },
  fonts: [
    { provider: fontProviders.fontsource(), name: "Inter", cssVariable: "--font-inter", weights: [400, 500, 600] },
  ],
  integrations: [
    starlight({
      title: "HealthDojo",
      description: "An open, synthetic benchmark prototype for how vision models spot fall and dementia hazards in homes.",
      social: [{ icon: "github", label: "GitHub", href: "https://github.com/pistachiopranay/healthdojo" }],
      sidebar: [
        { label: "Results", items: [
          { label: "Leaderboard", link: "/results/#leaderboard" },
          { label: "Difficulty curve", link: "/results/#difficulty-curve" },
          { label: "Hardest hazards", link: "/results/#hardest-hazards-in-this-sample" },
          { label: "Heatmaps", link: "/results/#heatmaps" },
          { label: "Open any room", link: "/results/#open-any-room" },
        ] },
        { label: "Method", items: [
          { label: "From guidance to a test", link: "/method/#from-guidance-to-a-test" },
          { label: "Rubric browser", link: "/method/#rubric-browser" },
          { label: "Difficulty levels", link: "/method/#five-difficulty-levels" },
          { label: "Limits", link: "/method/#limits" },
        ] },
        { label: "Elsewhere", items: [
          { label: "Overview", link: "/" },
          { label: "Explore", link: "/explore/" },
        ] },
      ],
      customCss: ["./src/styles/starlight.css"],
      components: {
        ThemeSelect: "./src/overrides/Empty.astro",
        ThemeProvider: "./src/overrides/ThemeProvider.astro",
      },
      plugins: [starlightThemeBlack({ navLinks: NAV, docs: { showMarkdownActions: false } })],
    }),
  ],
});
