import React from "react";
import clsx from "clsx";
import Link from "@docusaurus/Link";

export default function PaginatorNavLink(props) {
  /**
   * Do not display the "Previous" and "Next" labels.
   */
  const shouldDisplayPreviousNextLabels = false;
  const subLabel = shouldDisplayPreviousNextLabels;

  const { permalink, title, isNext } = props;

  return (
    <Link
      className={clsx(
        "pagination-nav__link",
        isNext ? "pagination-nav__link--next" : "pagination-nav__link--prev"
      )}
      to={permalink}
    >
      {subLabel && <div className="pagination-nav__sublabel">{subLabel}</div>}
      <div className="pagination-nav__label">{title}</div>
    </Link>
  );
}
