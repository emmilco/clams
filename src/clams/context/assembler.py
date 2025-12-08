"""Context assembler for gathering and formatting multi-source context."""

import asyncio
from typing import Any

import structlog

from .deduplication import deduplicate_items
from .formatting import (
    assemble_markdown,
    format_code,
    format_commit,
    format_experience,
    format_memory,
    format_value,
)
from .models import ContextItem, FormattedContext, InvalidContextTypeError
from .searcher_types import Searcher
from .tokens import cap_item_tokens, distribute_budget, estimate_tokens

logger = structlog.get_logger()

# Valid context types
VALID_CONTEXT_TYPES = {"memories", "code", "experiences", "values", "commits"}


class ContextAssembler:
    """Assemble context from multiple sources for agent injection."""

    def __init__(self, searcher: Searcher):
        """
        Initialize assembler with searcher.

        Args:
            searcher: Searcher instance for querying all sources
        """
        self._searcher = searcher
        self._logger = logger.bind(component="context_assembler")

    async def assemble_context(
        self,
        query: str,
        context_types: list[str],
        limit: int = 20,
        max_tokens: int = 2000,
    ) -> FormattedContext:
        """
        Assemble context from specified sources.

        Queries all requested sources in parallel, deduplicates results,
        applies token budgets, and formats as markdown.

        Args:
            query: Natural language query describing what context is needed
            context_types: List of source types to query
            limit: Maximum items to retrieve per source (default: 20)
            max_tokens: Soft limit on total token count (default: 2000)

        Returns:
            FormattedContext with markdown text and metadata

        Raises:
            InvalidContextTypeError: If invalid context type requested
        """
        # Validate context types
        invalid = [t for t in context_types if t not in VALID_CONTEXT_TYPES]
        if invalid:
            raise InvalidContextTypeError(
                invalid[0],
                list(VALID_CONTEXT_TYPES),
            )

        self._logger.info(
            "assembling_context",
            query=query,
            context_types=context_types,
            limit=limit,
            max_tokens=max_tokens,
        )

        # Query all sources in parallel
        items_by_source = await self._query_sources(query, context_types, limit)

        # Deduplicate across sources
        all_items = []
        for items in items_by_source.values():
            all_items.extend(items)

        deduplicated = deduplicate_items(all_items)

        self._logger.info(
            "deduplication_complete",
            original_count=len(all_items),
            deduplicated_count=len(deduplicated),
        )

        # Distribute token budget
        token_budget = distribute_budget(context_types, max_tokens)

        # Select items within budget
        selected_by_source, truncated_ids = self._select_items(
            deduplicated, token_budget
        )

        # Format as markdown
        markdown = assemble_markdown(selected_by_source)
        token_count = estimate_tokens(markdown)

        # Build response
        all_selected = []
        sources_used = {}
        for source, items in selected_by_source.items():
            all_selected.extend(items)
            sources_used[source] = len(items)

        budget_exceeded = token_count > max_tokens

        if budget_exceeded:
            self._logger.warning(
                "token_budget_exceeded",
                budget=max_tokens,
                actual=token_count,
            )

        return FormattedContext(
            markdown=markdown,
            items=all_selected,
            token_count=token_count,
            sources_used=sources_used,
            budget_exceeded=budget_exceeded,
            truncated_items=truncated_ids,
        )

    async def get_premortem_context(
        self,
        domain: str,
        strategy: str | None = None,
        limit: int = 10,
        max_tokens: int = 1500,
    ) -> FormattedContext:
        """
        Get premortem warnings for a domain (and optionally strategy).

        Retrieves past failures, common surprises, and frequent root causes
        for the specified domain to help agent anticipate issues.

        Args:
            domain: Domain enum value (e.g., "debugging", "feature")
            strategy: Optional strategy enum value (e.g., "systematic-elimination")
            limit: Maximum items per category (default: 10)
            max_tokens: Soft limit on total tokens (default: 1500)

        Returns:
            FormattedContext with premortem warnings
        """
        self._logger.info(
            "assembling_premortem",
            domain=domain,
            strategy=strategy,
            limit=limit,
        )

        # Query all experience axes + values in parallel
        tasks = [
            # Full axis: failures in domain
            self._searcher.search_experiences(
                query=f"failures and issues in {domain}",
                axis="full",
                domain=domain,
                outcome="falsified",
                limit=limit,
            ),
            # Surprise axis: unexpected outcomes
            self._searcher.search_experiences(
                query=f"unexpected outcomes in {domain}",
                axis="surprise",
                domain=domain,
                limit=limit,
            ),
            # Root cause axis: why things fail
            self._searcher.search_experiences(
                query=f"why hypotheses fail in {domain}",
                axis="root_cause",
                domain=domain,
                limit=limit,
            ),
            # Values: principles for domain
            self._searcher.search_values(
                query=f"principles for {domain}"
                + (f" using {strategy}" if strategy else ""),
                limit=5,
            ),
        ]

        # Add strategy-specific query if strategy provided
        if strategy:
            tasks.insert(
                1,
                self._searcher.search_experiences(
                    query=f"outcomes using {strategy} strategy",
                    axis="strategy",
                    strategy=strategy,
                    limit=limit,
                ),
            )

        # Execute queries (return_exceptions=True to handle partial failures)
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results (handle partial failures gracefully)
        # Each result is either a list of search results or an Exception
        exp_full = results[0] if not isinstance(results[0], Exception) else []
        idx = 1

        if strategy:
            exp_strategy = (
                results[idx] if not isinstance(results[idx], Exception) else []
            )
            idx += 1
        else:
            exp_strategy = []

        exp_surprise = (
            results[idx] if not isinstance(results[idx], Exception) else []
        )
        exp_root_cause = (
            results[idx + 1] if not isinstance(results[idx + 1], Exception) else []
        )
        values = (
            results[idx + 2] if not isinstance(results[idx + 2], Exception) else []
        )

        # Log any partial failures
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self._logger.warning(
                    "premortem_query_partial_failure",
                    query_index=i,
                    error=str(result),
                )

        # Convert to ContextItems (only if results are valid lists)
        items: list[ContextItem] = []

        if isinstance(exp_full, list):
            for result in exp_full:
                items.append(self._experience_to_item(result, "full"))

        if isinstance(exp_strategy, list):
            for result in exp_strategy:
                items.append(self._experience_to_item(result, "strategy"))

        if isinstance(exp_surprise, list):
            for result in exp_surprise:
                items.append(self._experience_to_item(result, "surprise"))

        if isinstance(exp_root_cause, list):
            for result in exp_root_cause:
                items.append(self._experience_to_item(result, "root_cause"))

        if isinstance(values, list):
            for result in values:
                items.append(self._value_to_item(result))

        # Group by source for formatting
        items_by_source = {
            "experiences": [i for i in items if i.source == "experience"],
            "values": [i for i in items if i.source == "value"],
        }

        # Format as premortem markdown
        markdown = assemble_markdown(
            items_by_source,
            premortem=True,
            domain=domain,
            strategy=strategy,
        )
        token_count = estimate_tokens(markdown)

        sources_used = {
            "experiences": len(items_by_source["experiences"]),
            "values": len(items_by_source["values"]),
        }

        return FormattedContext(
            markdown=markdown,
            items=items,
            token_count=token_count,
            sources_used=sources_used,
            budget_exceeded=token_count > max_tokens,
        )

    async def _query_sources(
        self,
        query: str,
        context_types: list[str],
        limit: int,
    ) -> dict[str, list[ContextItem]]:
        """
        Query all requested sources in parallel.

        Args:
            query: Search query
            context_types: Sources to query
            limit: Max results per source

        Returns:
            Dict mapping source type to ContextItems
        """
        tasks: list[Any] = []
        source_order: list[str] = []

        for source in context_types:
            if source == "memories":
                tasks.append(self._searcher.search_memories(query, limit=limit))
                source_order.append("memories")
            elif source == "code":
                tasks.append(self._searcher.search_code(query, limit=limit))
                source_order.append("code")
            elif source == "experiences":
                tasks.append(
                    self._searcher.search_experiences(
                        query, axis="full", limit=limit
                    )
                )
                source_order.append("experiences")
            elif source == "values":
                tasks.append(self._searcher.search_values(query, limit=5))
                source_order.append("values")
            elif source == "commits":
                tasks.append(self._searcher.search_commits(query, limit=limit))
                source_order.append("commits")

        # Execute all queries in parallel
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            self._logger.error("source_query_failed", error=str(e))
            raise

        # Convert results to ContextItems
        items_by_source: dict[str, list[ContextItem]] = {}

        for source, result in zip(source_order, results):
            if isinstance(result, Exception):
                self._logger.warning(
                    "source_query_partial_failure",
                    source=source,
                    error=str(result),
                )
                items_by_source[source] = []
                continue

            # Result is a list of result objects (not an exception)
            items = self._convert_results(source, result)  # type: ignore[arg-type]
            items_by_source[source] = items

        return items_by_source

    def _convert_results(
        self,
        source: str,
        results: list[Any],
    ) -> list[ContextItem]:
        """
        Convert search results to ContextItems.

        Args:
            source: Source type
            results: List of typed result objects

        Returns:
            List of ContextItems
        """
        items = []

        for result in results:
            if source == "memories":
                content = format_memory(result.__dict__)
            elif source == "code":
                content = format_code(result.__dict__)
            elif source == "experiences":
                content = format_experience(result.__dict__)
            elif source == "values":
                content = format_value(result.__dict__)
            elif source == "commits":
                content = format_commit(result.__dict__)
            else:
                self._logger.warning("unknown_source_type", source=source)
                continue

            # Convert plural source to singular
            source_singular = source
            if source == "memories":
                source_singular = "memory"
            elif source == "experiences":
                source_singular = "experience"
            elif source == "values":
                source_singular = "value"
            elif source == "commits":
                source_singular = "commit"
            # "code" is already singular

            items.append(
                ContextItem(
                    source=source_singular,
                    content=content,
                    relevance=result.score,
                    metadata=result.__dict__,
                )
            )

        return items

    def _experience_to_item(
        self, result: Any, axis: str
    ) -> ContextItem:
        """Convert ExperienceResult to ContextItem."""
        content = format_experience(result.__dict__)
        metadata = result.__dict__.copy()
        metadata["axis"] = axis  # Add axis to metadata for premortem formatting
        return ContextItem(
            source="experience",
            content=content,
            relevance=result.score,
            metadata=metadata,
        )

    def _value_to_item(self, result: Any) -> ContextItem:
        """Convert ValueResult to ContextItem."""
        content = format_value(result.__dict__)
        return ContextItem(
            source="value",
            content=content,
            relevance=result.score,
            metadata=result.__dict__,
        )

    def _select_items(
        self,
        items: list[ContextItem],
        token_budget: dict[str, int],
    ) -> tuple[dict[str, list[ContextItem]], list[str]]:
        """
        Select items within token budget.

        Applies per-source and per-item token limits, truncating as needed.
        Redistributes unused budget from sources with few results to sources
        that could use more tokens.

        Args:
            items: Deduplicated items (all sources)
            token_budget: Token budget per source

        Returns:
            Tuple of (items_by_source, truncated_item_ids)
        """
        # Group items by source
        by_source: dict[str, list[ContextItem]] = {}
        for item in items:
            # Convert singular source back to plural
            source_plural = item.source
            if item.source == "memory":
                source_plural = "memories"
            elif item.source == "experience":
                source_plural = "experiences"
            elif item.source == "value":
                source_plural = "values"
            elif item.source == "commit":
                source_plural = "commits"
            # "code" stays as "code"

            if source_plural not in by_source:
                by_source[source_plural] = []
            by_source[source_plural].append(item)

        # First pass: select items for each source within budget
        selected: dict[str, list[ContextItem]] = {}
        truncated_ids: list[str] = []
        unused_budget: dict[str, int] = {}

        for source, source_items in by_source.items():
            budget = token_budget.get(source, 0)
            if budget == 0:
                continue

            selected[source] = []
            used_tokens = 0

            # Sort by relevance (already sorted from deduplication)
            for item in source_items:
                # Apply per-item cap
                # (pass item.source for context-aware truncation notes)
                capped_content, was_truncated = cap_item_tokens(
                    item.content, budget, item.metadata, item.source
                )

                if was_truncated:
                    truncated_ids.append(item.metadata.get("id", "unknown"))

                item_tokens = estimate_tokens(capped_content)

                # Check if item fits in remaining budget
                if used_tokens + item_tokens > budget:
                    # No more room in budget for this source
                    break

                # Add item with possibly capped content
                selected_item = ContextItem(
                    source=item.source,
                    content=capped_content,
                    relevance=item.relevance,
                    metadata=item.metadata,
                )
                selected[source].append(selected_item)
                used_tokens += item_tokens

            # Track unused budget for redistribution
            unused = budget - used_tokens
            if unused > 0:
                unused_budget[source] = unused

            self._logger.debug(
                "source_budget_used",
                source=source,
                budget=budget,
                used=used_tokens,
                unused=unused,
                items_selected=len(selected[source]),
            )

        # Second pass: redistribute unused budget to sources that need more
        total_unused = sum(unused_budget.values())
        if total_unused > 0:
            self._logger.debug(
                "redistributing_unused_budget",
                total_unused=total_unused,
            )

            # Find sources that hit their budget limit (have more items available)
            sources_needing_more = [
                source
                for source in by_source.keys()
                if source in selected
                and len(by_source[source]) > len(selected[source])
            ]

            if sources_needing_more:
                # Distribute unused budget proportionally by original weight
                extra_per_source = total_unused // len(sources_needing_more)

                for source in sources_needing_more:
                    original_budget = token_budget.get(source, 0)
                    new_budget = original_budget + extra_per_source
                    used_tokens = sum(
                        estimate_tokens(item.content) for item in selected[source]
                    )

                    # Try to add more items with extra budget
                    for item in by_source[source][len(selected[source]) :]:
                        capped_content, was_truncated = cap_item_tokens(
                            item.content, new_budget, item.metadata, item.source
                        )

                        if was_truncated:
                            truncated_ids.append(
                                item.metadata.get("id", "unknown")
                            )

                        item_tokens = estimate_tokens(capped_content)

                        if used_tokens + item_tokens > new_budget:
                            break

                        selected_item = ContextItem(
                            source=item.source,
                            content=capped_content,
                            relevance=item.relevance,
                            metadata=item.metadata,
                        )
                        selected[source].append(selected_item)
                        used_tokens += item_tokens

                    self._logger.debug(
                        "redistributed_budget_used",
                        source=source,
                        extra_budget=extra_per_source,
                        new_total_items=len(selected[source]),
                    )

        return selected, truncated_ids
