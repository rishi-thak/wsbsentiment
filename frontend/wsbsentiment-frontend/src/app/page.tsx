"use client";

import React, { useState } from "react";

type Comment = {
  id: string;
  body: string;
  sentiment: number;
  score: number;
  author: string;
  created_utc: number;
};

type PostData = {
  id: string;
  title: string;
  selftext: string;
  sentiment: number;
  score: number;
  url: string;
  num_comments: number;
  created_utc: number;
  top_comments: Comment[];
};

export default function Home() {
  const [url, setUrl] = useState("");
  const [maxComments, setMaxComments] = useState(50);
  const [data, setData] = useState<PostData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function fetchSentiment() {
    setLoading(true);
    setError(null);
    setData(null);

    // Simplified validation: just check it includes reddit.com
    if (!url.includes("reddit.com")) {
      setError("Please enter a valid Reddit post URL");
      setLoading(false);
      return;
    }

    try {
      const res = await fetch(
        `/api/analyze_post?url=${encodeURIComponent(url)}&max_comments=${maxComments}`
      );
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to fetch sentiment");
      }
      const json: PostData = await res.json();
      setData(json);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="max-w-3xl mx-auto p-4">
      <h1 className="text-3xl font-bold mb-6">WSB Reddit Sentiment Analyzer</h1>

      <div className="mb-4">
        <label htmlFor="url" className="block font-semibold mb-1">
          Reddit Post URL
        </label>
        <input
          id="url"
          type="text"
          placeholder="https://www.reddit.com/r/wallstreetbets/comments/abc123/..."
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          className="w-full border border-gray-300 rounded px-3 py-2"
        />
      </div>

      <div className="mb-4">
        <label htmlFor="maxComments" className="block font-semibold mb-1">
          Max Comments to Analyze
        </label>
        <input
          id="maxComments"
          type="number"
          min={1}
          max={500}
          value={maxComments}
          onChange={(e) => setMaxComments(Number(e.target.value))}
          className="w-24 border border-gray-300 rounded px-3 py-2"
        />
      </div>

      <button
        onClick={fetchSentiment}
        disabled={loading || !url}
        className="bg-blue-600 text-white rounded px-4 py-2 disabled:opacity-50"
      >
        {loading ? "Analyzing..." : "Analyze"}
      </button>

      {error && <p className="mt-4 text-red-600">{error}</p>}

      {data && (
        <section className="mt-8">
          <h2 className="text-2xl font-bold mb-2">{data.title}</h2>
          <p className="mb-2 text-sm text-gray-600">
            Score: {data.score} | Comments: {data.num_comments} | Sentiment:{" "}
            {data.sentiment.toFixed(3)}
          </p>
          <p className="mb-4 whitespace-pre-wrap">{data.selftext || "(No text)"}</p>

          <h3 className="text-xl font-semibold mb-2">Top Comments</h3>
          <ul className="space-y-4 max-h-[400px] overflow-y-auto">
            {data.top_comments.map((comment) => (
              <li
                key={comment.id}
                className={`p-3 rounded border ${
                  comment.sentiment > 0.1
                    ? "bg-green-100 border-green-300"
                    : comment.sentiment < -0.1
                    ? "bg-red-100 border-red-300"
                    : "bg-gray-100 border-gray-300"
                }`}
              >
                <p className="mb-1 text-sm text-gray-700">{comment.body}</p>
                <div className="text-xs text-gray-500 flex justify-between">
                  <span>Sentiment: {comment.sentiment.toFixed(3)}</span>
                  <span>Score: {comment.score}</span>
                  <span>By: {comment.author}</span>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
