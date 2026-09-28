// @ts-check
import { defineConfig, fontProviders } from "astro/config";
import starlight from "@astrojs/starlight";
import starlightThemeBlack from "starlight-theme-black";

const NAV = [
  { label: "Overview", link: "/" },
  { label: "How it works", link: "/method/" },
  { label: "Explore", link: "/explore/" },
  { label: "Early results", link: "/results/" },
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
      social: [{ icon: "linkedin", label: "Pranay Madan on LinkedIn", href: "https://www.linkedin.com/in/pranaymadan/" }, { icon: "github", label: "GitHub", href: "https://github.com/pistachiopranay/healthdojo" }],
      sidebar: [
        { label: "How it works", items: [
          { label: "From guidance to a test", link: "/method/#from-guidance-to-a-test" },
          { label: "Rubric browser", link: "/method/#rubric-browser" },
          { label: "Difficulty levels", link: "/method/#five-difficulty-levels" },
          { label: "Limits", link: "/method/#limits" },
        ] },
        { label: "Early results", items: [
          { label: "Leaderboard", link: "/results/#leaderboard" },
          { label: "Difficulty curve", link: "/results/#difficulty-curve" },
          { label: "Hardest hazards", link: "/results/#hardest-hazards-in-this-sample" },
          { label: "Heatmaps", link: "/results/#heatmaps" },
          { label: "Open any room", link: "/results/#open-any-room" },
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
