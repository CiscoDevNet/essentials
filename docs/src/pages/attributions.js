export default function Attributions() {
  const { siteConfig } = useDocusaurusContext();
  return (
    <Layout description={`${siteConfig.title} attributions`}>
      <main>
        <p>
          Essential oil photo by{" "}
          <a href="https://unsplash.com/@kellysikkema?utm_source=unsplash&utm_medium=referral&utm_content=creditCopyText">
            Kelly Sikkema
          </a>{" "}
          on{" "}
          <a href="https://unsplash.com/collections/2_Tj8tPGHkk/essentials/23b02dc02283231be5548e6dcd1232ed?utm_source=unsplash&utm_medium=referral&utm_content=creditCopyText">
            Unsplash
          </a>
        </p>
        <p>
          Essential chalkboard photo by{" "}
          <a href="https://unsplash.com/@sharonmccutcheon?utm_source=unsplash&utm_medium=referral&utm_content=creditCopyText">
            Sharon McCutcheon
          </a>{" "}
          on{" "}
          <a href="https://unsplash.com/s/photos/essential?utm_source=unsplash&utm_medium=referral&utm_content=creditCopyText">
            Unsplash
          </a>
        </p>
        ;
      </main>
    </Layout>
  );
}
