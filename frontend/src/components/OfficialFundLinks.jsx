import React from "react";
import "./officialFundLinks.css";
import { officialFundLinks } from "../data/officialFundLinks";

function LinkCard({ item }) {
  return (
    <a
      href={item.url}
      target="_blank"
      rel="noreferrer"
      className="officialLink-card"
    >
      <div className="officialLink-amc">{item.amc}</div>
      <div className="officialLink-fund">{item.fund}</div>
      <div className="officialLink-open">Open official page →</div>
    </a>
  );
}

function LinkSection({ title, items }) {
  if (!items || !items.length) return null;

  return (
    <div className="officialLink-section">
      <h4 className="officialLink-sectionTitle">{title}</h4>
      <div className="officialLink-grid">
        {items.map((item, idx) => (
          <LinkCard key={`${item.amc}-${item.fund}-${idx}`} item={item} />
        ))}
      </div>
    </div>
  );
}

export default function OfficialFundLinks() {
  const { active, passive } = officialFundLinks;

  return (
    <div className="officialLink-wrap">
      <div className="officialLink-header">
        <h3>Official Fund Links</h3>
        <p>
          Direct official AMC pages for selected active and passive mutual
          funds.
        </p>
      </div>

      <div className="officialLink-block">
        <h3 className="officialLink-mainTitle">Active Funds</h3>

        <LinkSection title="Large Cap" items={active.largeCap} />
        <LinkSection title="Mid Cap" items={active.midCap} />
        <LinkSection title="Small Cap" items={active.smallCap} />
      </div>

      <div className="officialLink-block">
        <h3 className="officialLink-mainTitle">Passive Funds</h3>

        <LinkSection title="Nifty 50" items={passive.nifty50} />
        <LinkSection title="BSE / Sensex" items={passive.bse} />
        <LinkSection title="Nifty Midcap 150" items={passive.midcap150} />
        <LinkSection title="Nifty Smallcap 250" items={passive.smallcap250} />
      </div>
    </div>
  );
}