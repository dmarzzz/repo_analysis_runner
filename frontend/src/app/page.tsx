import Image from "next/image";
import styles from "./page.module.css";

export default function Home() {
  return (
    <div>
      <h1>Welcome to the Frontend</h1>
      <p>This is a simple frontend application for deployment on Vercel.</p>
      <h2>Main Page</h2>
      <a href="/index.html">Go to Main Index</a>
      <h2>Weekly Reports</h2>
      <ul>
        <li><a href="/weekly_report/EIPs">EIPs</a></li>
        <li><a href="/weekly_report/RIPs">RIPs</a></li>
        <li><a href="/weekly_report/L2-interop">L2-interop</a></li>
        <li><a href="/weekly_report/reth">reth</a></li>
        <li><a href="/weekly_report/eliza">eliza</a></li>
        <li><a href="/weekly_report/optimism">optimism</a></li>
        <li><a href="/weekly_report/rbuilder">rbuilder</a></li>
        <li><a href="/weekly_report/rollup-boost">rollup-boost</a></li>
        <li><a href="/weekly_report/nitro">nitro</a></li>
      </ul>
    </div>
  );
}
