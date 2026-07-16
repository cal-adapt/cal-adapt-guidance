--[[
Adds a "Citation" section to PDF output, built from each page's existing
`author`/`title`/`date`/`citation` metadata.

Why this exists: Quarto auto-generates a "cite this work as" appendix for
HTML (`appendix-cite-as`, set in _quarto.yml), but that feature is tagged
`formats: [$html-doc]` in Quarto's own schema -- it has no PDF/LaTeX
equivalent. This filter recreates the same citation text for PDF so both
formats show a "how to cite" block, without duplicating content in every
.qmd file.

Registered in _quarto.yml under format.pdf.filters.

Layout of this file:
  1. format_person / format_author_entry / join_authors -- turn the
     `author` metadata (organization or one/more people) into an
     APA-style author string, e.g. "Machuca, V., & Ford, V."
  2. citation_field -- reads a field (publisher/issued) from the page's
     `citation:` metadata block, if it has one.
  3. page_url -- rebuilds the page's canonical https://analytics.cal-adapt.org
     URL from its source file path.
  4. Pandoc(doc) -- the filter entry point: assembles the pieces above
     and inserts the "Citation" section at the top of the document, just
     below the title.
]]

local site_url = "https://analytics.cal-adapt.org"

-- "Vanessa Machuca" -> "Machuca, V." (APA-style: family name, given initial)
local function format_person(full_name)
  local words = {}
  for w in full_name:gmatch("%S+") do
    table.insert(words, w)
  end
  if #words <= 1 then
    return full_name
  end
  local family = words[#words]
  local given_initial = words[1]:sub(1, 1)
  return family .. ", " .. given_initial .. "."
end

-- Each entry in the `author:` list is one of:
--   - an organization:      { name = { literal = "Cal-Adapt" } }
--   - a structured person:  { name = { family = "...", given = "..." } }
--   - a plain string, parsed by pandoc as MetaInlines: "Vanessa Machuca"
local function format_author_entry(entry)
  if type(entry) == "table" and entry.name ~= nil then
    local name = entry.name
    if type(name) == "table" and name.literal ~= nil then
      return pandoc.utils.stringify(name.literal)
    end
    if type(name) == "table" and (name.family ~= nil or name.given ~= nil) then
      local family = name.family and pandoc.utils.stringify(name.family) or ""
      local given = name.given and pandoc.utils.stringify(name.given) or ""
      if given ~= "" then
        return family .. ", " .. given:sub(1, 1) .. "."
      end
      return family
    end
    return format_person(pandoc.utils.stringify(name))
  end
  return format_person(pandoc.utils.stringify(entry))
end

-- APA-style joining: "A." / "A, & B." / "A, B, & C."
local function join_authors(names)
  local n = #names
  if n == 0 then
    return ""
  elseif n == 1 then
    return names[1]
  elseif n == 2 then
    return names[1] .. ", & " .. names[2]
  else
    return table.concat(names, ", ", 1, n - 1) .. ", & " .. names[n]
  end
end

-- Reads `citation.<key>` from the page's front matter, if present.
-- Returns nil if the page has no `citation:` block or the key is unset.
local function citation_field(citation, key)
  if type(citation) == "table" and citation[key] then
    return pandoc.utils.stringify(citation[key])
  end
  return nil
end

-- Rebuilds the page's canonical URL, e.g.
-- scientific-guidance/census-tracts.qmd -> .../scientific-guidance/census-tracts.html
-- Mirrors the link Quarto's own HTML citation appendix points to.
local function page_url()
  local relative_path = quarto.doc.input_file
  if quarto.project.directory and quarto.project.directory ~= "" then
    local ok, made_relative = pcall(pandoc.path.make_relative, quarto.doc.input_file, quarto.project.directory)
    if ok and made_relative then
      relative_path = made_relative
    end
  end
  relative_path = relative_path:gsub("%.[Qq][Mm][Dd]$", ".html")
  relative_path = relative_path:gsub("/index%.html$", "/") -- e.g. foo/index.html -> foo/
  return site_url .. "/" .. relative_path
end

function Pandoc(doc)
  if not quarto.doc.is_format("pdf") then
    return doc
  end

  local meta = doc.meta
  local citation = meta.citation
  if citation == false then
    return doc -- page opted out, same as the HTML citation appendix
  end

  local authors = {}
  for _, entry in ipairs(meta.author or {}) do
    table.insert(authors, format_author_entry(entry))
  end
  local author_str = join_authors(authors)
  if author_str == "" then
    author_str = "Cal-Adapt"
  end

  local date_str = citation_field(citation, "issued")
    or (meta["date-modified"] and pandoc.utils.stringify(meta["date-modified"]))
    or (meta.date and pandoc.utils.stringify(meta.date))
  local year = date_str and date_str:match("%d%d%d%d") or nil

  local publisher = citation_field(citation, "publisher") or "Cal-Adapt"
  local title = meta.title and pandoc.utils.stringify(meta.title) or ""
  local url = page_url()

  -- "Author(s). (Year)." -- skip the extra period if the author string
  -- already ends in one (e.g. a single-initial name like "Ford, V.")
  local lead = author_str
  if not lead:match("%.$") then
    lead = lead .. "."
  end
  if year then
    lead = lead .. " (" .. year .. ")."
  end

  -- The mdframed environment (defined in _quarto.yml's include-in-header)
  -- wraps the citation in a bordered, brand-colored box.
  local citation_blocks = {
    pandoc.RawBlock("latex", "\\begin{citebox}\\small"),
    pandoc.Para({ pandoc.Str("For attribution, please cite this work as:") }),
    pandoc.Para({
      pandoc.Str(lead .. " "),
      pandoc.Emph({ pandoc.Str(title) }),
      pandoc.Str(". " .. publisher .. ". "),
      pandoc.Link({ pandoc.Str(url) }, url),
    }),
    pandoc.RawBlock("latex", "\\end{citebox}"),
  }
  for i = #citation_blocks, 1, -1 do
    doc.blocks:insert(1, citation_blocks[i])
  end

  return doc
end
