"use client";

import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";

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

    if (!url.includes("reddit.com")) {
      setError("Please enter a valid Reddit post URL");
      setLoading(false);
      return;
    }

    try {
      // IMPORTANT: Call your FastAPI backend directly here
      const res = await fetch(
        `http://localhost:8000/analyze_post?url=${encodeURIComponent(
          url
        )}&max_comments=${maxComments}`
      );
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to fetch sentiment");
      }
      const json: PostData = await res.json();
      setData(json);
    } catch (e: unknown) {
      if (e instanceof Error) {
        setError(e.message);
      } else {
        setError(String(e));
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="max-w-3xl mx-auto p-6">
      <h1 className="text-4xl font-extrabold mb-8 text-sky-600 dark:text-sky-400">
        WSB Reddit Sentiment Analyzer
      </h1>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          fetchSentiment();
        }}
        className="space-y-6"
      >
        <div>
          <Label
            htmlFor="url"
            className="mb-1 block font-semibold text-gray-300"
          >
            Reddit Post URL
          </Label>
          <Input
            id="url"
            type="url"
            placeholder="https://www.reddit.com/r/wallstreetbets/comments/abc123/..."
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            className="bg-gray-900 border-sky-600 focus:ring-sky-500"
            required
          />
        </div>

        <div>
          <Label
            htmlFor="maxComments"
            className="mb-1 block font-semibold text-gray-300"
          >
            Max Comments to Analyze
          </Label>
          <Input
            id="maxComments"
            type="number"
            min={1}
            max={500}
            value={maxComments}
            onChange={(e) => setMaxComments(Number(e.target.value))}
            className="w-28 bg-gray-900 border-sky-600 focus:ring-sky-500"
            required
          />
        </div>

        <Button
          type="submit"
          disabled={loading || !url}
          className="bg-sky-600 hover:bg-sky-700 disabled:opacity-50 w-full"
        >
          {loading ? "Analyzing..." : "Analyze"}
        </Button>
      </form>

      {error && (
        <p className="mt-6 text-red-500 font-medium" role="alert">
          {error}
        </p>
      )}

      {data && (
        <section className="mt-10">
          <h2 className="text-3xl font-bold text-sky-500 mb-2">{data.title}</h2>
          <p className="text-sm text-gray-400 mb-4">
            Score: <span className="font-semibold">{data.score}</span> | Comments:{" "}
            <span className="font-semibold">{data.num_comments}</span> | Sentiment:{" "}
            <span className="font-semibold">{data.sentiment.toFixed(3)}</span>
          </p>

          <Card className="mb-8 bg-gray-900 border border-sky-700 p-5">
            <p className="whitespace-pre-wrap text-gray-300">
              {data.selftext || "(No text)"}
            </p>
          </Card>

          <h3 className="text-2xl font-semibold text-sky-400 mb-4">Top Comments</h3>

          <ScrollArea className="max-h-[400px] rounded border border-sky-700 bg-gray-900 p-4">
            <ul className="space-y-5">
              {data.top_comments.map((comment) => {
                if (/mod|bot/i.test(comment.author)) return null;
                if (comment.body === "[deleted]" || comment.body === "[removed]")
                  return null;

                const sentimentClass =
                  comment.sentiment > 0.1
                    ? "bg-green-900 border-green-600"
                    : comment.sentiment < -0.1
                    ? "bg-red-900 border-red-600"
                    : "bg-gray-800 border-gray-700";

                return (
                  <li
                    key={comment.id}
                    className={`p-4 rounded border ${sentimentClass} text-gray-300`}
                  >
                    <p className="mb-2">{comment.body}</p>
                    <div className="text-xs flex flex-wrap justify-between text-gray-400 gap-2">
                      <span>Sentiment: {comment.sentiment.toFixed(3)}</span>
                      <span>Score: {comment.score}</span>
                      <span>By: {comment.author}</span>
                      <span>{new Date(comment.created_utc * 1000).toLocaleString()}</span>
                    </div>
                  </li>
                );
              })}
            </ul>
          </ScrollArea>
        </section>
      )}
    </main>
  );
}
