import CodeBlock from "@theme/CodeBlock";
import React from "react";
import Layout from "@theme/Layout";
import useDocusaurusContext from "@docusaurus/useDocusaurusContext";

export default function QuickStart() {
  const { siteConfig } = useDocusaurusContext();
  return (
    <Layout
      title={`Quickstart`}
      description="Description will go into a meta tag in <head />"
    >
      <main>
        <p>Hello world</p>
        <CodeBlock className="language-javascript">
          {`jsx {1,4-6,11}
import React from 'react';

function MyComponent(props) {
  if (props.isBar) {
    return <div>Bar</div>;
  }

  return <div>Foo</div>;
}

export default MyComponent;
`}
        </CodeBlock>
      </main>
    </Layout>
  );
}
