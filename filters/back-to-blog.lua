--[[
Adds a "Back to Blog" link to the top of every post under blog/posts/.

Why this exists: blog posts aren't part of any sidebar, so Quarto's own
bread-crumbs feature (bread-crumbs: true in _quarto.yml) doesn't surface a
way back to the blog listing from an individual post. This used to be
injected by client-side JS after the page loaded, which caused a flash of
missing content and left non-JS clients with nothing. A Lua filter runs at
render time instead, so the link is baked into the static HTML.

It lands as the first block of body content -- below the auto-generated
title/date/category-badge header (that header comes from doc.meta, not
doc.blocks, so a Pandoc filter can't place anything above it) and above the
post's own content.

Registered in blog/posts/_metadata.yml under format.html.filters.
]]

local function is_blog_post()
  local path = quarto.doc.input_file
  if quarto.project.directory and quarto.project.directory ~= "" then
    local ok, made_relative = pcall(pandoc.path.make_relative, quarto.doc.input_file, quarto.project.directory)
    if ok and made_relative then
      path = made_relative
    end
  end
  return path:match("^blog/posts/") ~= nil
end

function Pandoc(doc)
  if not quarto.doc.is_format("html") or not is_blog_post() then
    return doc
  end

  local attr = pandoc.Attr("", { "back-to-blog" }, {})
  local link = pandoc.Link(
    { pandoc.RawInline("html", '<i class="bi bi-arrow-left"></i> '), pandoc.Str("Back to Blog") },
    "/blog/",
    "",
    attr
  )
  doc.blocks:insert(1, pandoc.Para({ link }))

  return doc
end
