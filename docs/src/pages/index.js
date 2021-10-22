import React from "react";
import clsx from "clsx";
import Layout from "@theme/Layout";
import Link from "@docusaurus/Link";
import useDocusaurusContext from "@docusaurus/useDocusaurusContext";
import styles from "./index.module.css";
import HomepageFeatures from "../components/HomepageFeatures";

function HomepageHeader() {
  const { siteConfig } = useDocusaurusContext();
  return (
    <header className={clsx("hero hero--primary", styles.heroBanner)}>
      <div className="container">
        <h1 className="hero__title">{siteConfig.title}</h1>
        <p className="hero__subtitle">{siteConfig.tagline}</p>
        <div className={styles.buttons}>
          <Link className="button button--primary button--lg" to="/docs">
            Read the Docs 📖
          </Link>
        </div>
      </div>
    </header>
  );
}

function PhotoAttribution() {
  // <p>
  //   Photo by{" "}
  //   <a href="https://unsplash.com/@sharonmccutcheon?utm_source=unsplash&utm_medium=referral&utm_content=creditCopyText">
  //     Sharon McCutcheon
  //   </a>{" "}
  //   on{" "}
  //   <a href="https://unsplash.com/s/photos/essential?utm_source=unsplash&utm_medium=referral&utm_content=creditCopyText">
  //     Unsplash
  //   </a>
  // </p>;

  return (
    <p>
      Photo by{" "}
      <a href="https://unsplash.com/@dsmacinnes?utm_source=unsplash&utm_medium=referral&utm_content=creditCopyText">
        Danielle MacInnes
      </a>{" "}
      on{" "}
      <a href="https://unsplash.com/s/photos/developer-love?utm_source=unsplash&utm_medium=referral&utm_content=creditCopyText">
        Unsplash
      </a>
    </p>
  );
}

export default function Home() {
  const { siteConfig } = useDocusaurusContext();
  return (
    <Layout description={`${siteConfig.title} home page`}>
      <HomepageHeader />
      <main>
        <HomepageFeatures />
      </main>
    </Layout>
  );
}
