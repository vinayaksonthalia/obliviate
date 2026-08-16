# Distributed vector index (C-SPANN)

Nodes carry a `VECTOR(384)` embedding (fastembed `bge-small-en-v1.5`) indexed with
CockroachDB's C-SPANN index:

```sql
CREATE VECTOR INDEX nodes_embedding_idx ON nodes (embedding vector_cosine_ops);
```

Recall is cosine ANN with the `<=>` operator:

```sql
SELECT id, weight, (embedding <=> $1) AS dist
FROM nodes
WHERE workspace = $2 AND deleted_at IS NULL AND embedding IS NOT NULL
ORDER BY embedding <=> $1
LIMIT $3;
```

The important part: this is **index-backed, not a full scan**. `EXPLAIN` on the query
shows a `top-k` + lookup join on the vector index — confirmed in our smoke tests. The
vectors live in the *same table* as the graph and the encrypted documents, so a
`forget` removes the row and its vector in the same transaction. There is no second
store to fall out of sync — which is exactly the gap the *Ghost Vectors* paper exploits
in bolt-on vector databases.
