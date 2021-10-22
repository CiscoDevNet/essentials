import React from "react";
import clsx from "clsx";
import styles from "./HomepageFeatures.module.css";

const FeatureList = [
  {
    title: "Build",
    Svg: require("../../static/img/undraw_build_bot.svg").default,
    description: (
      <>
        Create intelligent bots with Adaptive Cards. Containerize them with
        Docker.
      </>
    ),
  },
  {
    title: "Release",
    Svg: require("../../static/img/undraw_launch.svg").default,
    description: <>Launch your app with a few simple commands.</>,
  },
  {
    title: "Run",
    Svg: require("../../static/img/undraw_run.svg").default,
    description: (
      <>
        Run your applications in the Cloud with Google or OpenShift. Extend to
        run on more Cloud platforms.
      </>
    ),
  },
];

function Feature({ Svg, title, description }) {
  return (
    <div className={clsx("col col--4")}>
      <div className="text--center">
        <Svg className={styles.featureSvg} alt={title} />
      </div>
      <div className="text--center padding-horiz--md">
        <h3>{title}</h3>
        <p>{description}</p>
      </div>
    </div>
  );
}

export default function HomepageFeatures() {
  return (
    <section className={styles.features}>
      <div className="container">
        <div className="row">
          {FeatureList.map((props, idx) => (
            <Feature key={idx} {...props} />
          ))}
        </div>
      </div>
    </section>
  );
}
