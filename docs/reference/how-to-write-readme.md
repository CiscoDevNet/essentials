# How to Write a README

Source: http://blog.nodejitsu.com/how-to-write-a-readme
Author: Joshua Holbrook (http://jesusabdullah.github.com/)

Originally written for [jesusabdullah.github.com](http://jesusabdullah.github.com/) while writing documentation for the [Flatiron](https://github.com/flatiron) framework. Flatiron's documentation followed [standards and guidelines](https://gist.github.com/1363524) very similar to these.

---

## 1. Write an Example, Right Now

The very first thing in a readme should be a short example code snippet. It should show what your library does and as little else as possible. People should *be able to infer from your example how your library works*.

For example, [mkdirp](https://github.com/substack/node-mkdirp) by SubStack:

> **mkdirp**
>
> Like `mkdir -p`, but in node.js!
>
> **Example** — pow.js
>
> Output pow! And now /tmp/foo/bar/baz exists, huzzah!

In **four lines**, a programmer fluent in JavaScript can tell that `mkdirp`:

- Is a function.
- Takes 3 arguments: a *file path*, some *octal permissions*, and *an errorback*.
- Probably makes directories.

Add in the mention of "like mkdir -p" and, without any other documentation, we can tell how it works.

Not all projects can cover 100% of the API in one example, but they can still strive to get a common use case across. Another good example is [node-tap](https://github.com/isaacs/node-tap) — the example saves what would otherwise be a terrible readme.

### Why?

Your readme is your library's best chance of "selling" your library, and you **don't have that much time**.

When a developer starts looking at libraries, they're thinking two things:

1. Does this project solve my problem?
2. If so, how?

They're also looking at your competition and aren't very patient. A *good* example tells a developer right away if the module does what they need, and *any* example gives a taste of your API.

You also get the benefit of "sanity checking" your API. Does anything look bulky? Could the API be more obvious? Now you know.

---

## 2. Describe the Install Procedure

A project that does a good job of this is [hook.io](https://github.com/hookio/hook.io):

> **Getting Started / Demo**
>
> Now run:
>
> Spawn up as many as you want. The first one becomes a server, the rest become clients. Each helloworld hook emits a hello on an interval. Now watch the i/o party go!

**Two lines.** You now know how to get up and going with hook.io.

Ease of installation is another selling point. If you're not lucky enough to have an easy installation procedure, this section becomes even more important. For a complicated yet poorly-documented install, developers *will* screw it up and either complain or give up.

### Why?

Assuming your example made a sale, the second question a developer will ask is, "How do I install this thing?" Make it easy for them.

---

## 3. Stub Out the API Docs

Now that you have a basic example and installation instructions, document the basic API. Start with obvious entry points and work from there.

For example, from [union](https://github.com/flatiron/union):

> ### union.createServer(options)
>
> The `options` object is required. Options include:
>
> **options.before** — an array of middlewares used to route and serve incoming requests. Union's request handling is [connect](https://github.com/senchalabs/connect)-compatible, meaning all existing connect middlewares should work out-of-the-box.
>
> **options.after** — an array of stream filters applied after the request handlers in `options.before`. Stream filters inherit from `union.ResponseStream`, which implements the Node.js core streams API with additional features. The advantage is they don't require buffering the entire stream.
>
> **options.limit** *(optional)* — passed to internal instantiations of `union.BufferedStream`.

### Why?

You may be tempted to think an example is "enough." This is true only in very rare cases. Even `mkdirp` could use a short paragraph explaining arguments and behavior. Inference is great but shouldn't be completely relied upon. Be straightforward.

---

## 4. Tests

If your module has tests, describe how to run them. Keep it simple — like `npm test`.

> **Run Tests**
>
> Tests are written in vows and give complete coverage of all APIs and storage engines.

### Why?

Testing directions should be as straightforward as possible. One-liner commands are ideal.

---

## 5. Licensing and Contributors

Tag on your license and contributors. The content isn't critical in a readme context — a short mention is fine:

> **License:** MIT/X11.

### Why?

Commit logs already show who worked on the project. The license matters most for people who want to hack on your code, and most are fine with "It's MIT" when sending a pull request. You can scale this section later.

---

## 6. But I Had Other Stuff to Say!

Write a blog post about it. No, seriously.

A readme's scope should be limited to:

- What is it?
- How do I use it?

Anything else — like "Why I Wrote This Module" — doesn't fit. Blog posts are a **great** way of getting that information out.

Example: [Scaling Isomorphic Javascript Code](http://blog.nodejitsu.com/scaling-isomorphic-javascript-code) discusses the motivations behind [Flatiron](https://github.com/flatiron/flatiron). Great read for design pattern enthusiasts, but in a readme it would **only get in the way** of the user who just wants to write a webapp.

---

## TL;DR

If nothing else, **write an example**.
