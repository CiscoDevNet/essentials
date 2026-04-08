"""CIDR utilities."""

import ipaddress
from collections import defaultdict

_IPV6 = 6
_MIN_COLLAPSIBLE_GROUP = 2
AWS_EKS_MAX_PUBLIC_ACCESS_CIDRS = 40


def get_cidrs(ips: tuple[str, ...]) -> tuple[str, ...]:
    """Append a host prefix to bare IP addresses to produce CIDRs.

    IPv4 addresses get ``/32``; IPv6 addresses get ``/128``.
    Addresses that already contain a ``/`` are validated and passed through.

    Args:
        ips: Bare IP addresses or CIDR strings.

    Returns:
        Tuple of valid CIDR strings.

    Raises:
        ValueError: If any entry is empty, not a valid IP, or not a valid CIDR.
    """
    results: list[str] = []
    for ip in ips:
        if "/" in ip:
            ipaddress.ip_network(ip, strict=False)
            results.append(ip)
            continue
        addr = ipaddress.ip_address(ip)
        suffix = "/128" if addr.version == _IPV6 else "/32"
        results.append(f"{ip}{suffix}")
    return tuple(results)


def collapse_cidrs(
    cidrs: list[str],
    *,
    max_count: int = AWS_EKS_MAX_PUBLIC_ACCESS_CIDRS,
) -> list[str]:
    """Best-effort collapse of a CIDR list toward *max_count* entries.

    Strategy:

    1. Lossless merge via :func:`ipaddress.collapse_addresses` (per IP version).
    2. If still over *max_count*, repeatedly find the longest-prefix (narrowest)
       entries that share a common parent prefix and replace each group with
       its covering supernet, widening by one bit at a time.

    The result may still exceed *max_count* when the remaining networks have
    no collapsible sibling pairs (e.g., unrelated ``/32`` hosts across
    different subnets, or mixed IPv4/IPv6). Callers should check the length
    if a hard limit is required.

    Args:
        cidrs: CIDR strings (e.g. ``["10.0.0.0/8", "192.168.1.1/32"]``).
        max_count: Target maximum number of CIDRs in the result.

    Returns:
        Collapsed list of CIDR strings, ideally ``<= max_count``.

    Raises:
        ValueError: If *max_count* < 1, or if any entry is not a valid CIDR.
    """
    if max_count < 1:
        raise ValueError(f"max_count must be >= 1, got {max_count}")

    networks = [ipaddress.ip_network(c, strict=False) for c in cidrs]

    v4 = [n for n in networks if n.version != _IPV6]
    v6 = [n for n in networks if n.version == _IPV6]
    collapsed = list(ipaddress.collapse_addresses(v4)) + list(
        ipaddress.collapse_addresses(v6)
    )

    while len(collapsed) > max_count:
        best_parent: ipaddress.IPv4Network | ipaddress.IPv6Network | None = None
        member_indices: set[int] | None = None

        for candidate_prefix in sorted(
            {n.prefixlen for n in collapsed if n.prefixlen > 0}, reverse=True
        ):
            groups: dict[ipaddress.IPv4Network | ipaddress.IPv6Network, list[int]] = (
                defaultdict(list)
            )
            for idx, net in enumerate(collapsed):
                if net.prefixlen == candidate_prefix:
                    parent = net.supernet(prefixlen_diff=1)
                    groups[parent].append(idx)

            collapsible = {
                p: idxs
                for p, idxs in groups.items()
                if len(idxs) >= _MIN_COLLAPSIBLE_GROUP
            }
            if collapsible:
                best_parent = max(collapsible, key=lambda p: len(collapsible[p]))
                member_indices = set(collapsible[best_parent])
                break

        if best_parent is None or member_indices is None:
            break

        replaced = [n for i, n in enumerate(collapsed) if i not in member_indices]
        replaced.append(best_parent)
        collapsed = list(ipaddress.collapse_addresses(replaced))

    return [str(n) for n in collapsed]
