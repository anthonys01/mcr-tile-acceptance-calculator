"""
    Pattern generator utilities
"""
from typing import Iterator

from mahjong_objects import Constraint, Family


def pattern_generator(input_pattern: str) -> Iterator[str]:
    return _pattern_generator("", input_pattern, {}, {})


def _pattern_resolve_number_wildcards(parsed, to_parse, family_wildcards, number_wildcards,
                                      global_wildcard_parse, idx, character) -> list[Iterator]:
    min_wildcard = min(global_wildcard_parse)
    max_wildcard = max(global_wildcard_parse)
    if number_wildcards:
        new_number_wildcards = dict(number_wildcards)
        if min_wildcard not in new_number_wildcards:
            given_min = min(new_number_wildcards.keys())
            shift = ord(min_wildcard) - ord(given_min) + new_number_wildcards[given_min]
            if shift < 1 or shift > 9:
                return []
            new_number_wildcards[min_wildcard] = shift
        shift = new_number_wildcards[min_wildcard]

        max_wildcard_value = ord(max_wildcard) - ord(min_wildcard) + shift
        if max_wildcard_value > 9:
            return []
        new_number_wildcards[max_wildcard] = max_wildcard_value

        replaced = ""
        for wildcard in global_wildcard_parse:
            if wildcard not in new_number_wildcards:
                new_number_wildcards[wildcard] = ord(wildcard) - ord(min_wildcard) + shift
            replaced += str(new_number_wildcards[wildcard])
        return [_pattern_generator(parsed + replaced + character,
                                         to_parse[idx + 1:], family_wildcards, new_number_wildcards)]

    max_range = ord(max_wildcard) - ord(min_wildcard)
    max_shift = 10 - max_range
    iterators = []
    for shift in range(1, max_shift):
        number_wildcard = {}
        replaced = ""
        for wildcard in global_wildcard_parse:
            if wildcard not in number_wildcard:
                number_wildcard[wildcard] = ord(wildcard) - ord(min_wildcard) + shift
            replaced += str(number_wildcard[wildcard])
        iterators.append(_pattern_generator(parsed + replaced + character,
                                         to_parse[idx + 1:], family_wildcards, number_wildcard))
    return iterators

def _pattern_resolve_family_wildcard(parsed, to_parse, family_wildcards, number_wildcards,
                                     currently_parsed, global_wildcard_parse, idx, character) -> list[Iterator]:
    if character in family_wildcards:
        effectively_parsed = parsed
        if currently_parsed:
            effectively_parsed += currently_parsed + family_wildcards[character].value
        leftover = to_parse[idx + 1:]
        if global_wildcard_parse:
            leftover = global_wildcard_parse + family_wildcards[character].value + leftover
        return [_pattern_generator(effectively_parsed, leftover, family_wildcards, number_wildcards)]

    available_families = {Family.CHARACTER, Family.CIRCLE, Family.BAMBOO}
    available_families.difference_update(family_wildcards.values())
    iterators = []
    for family in available_families:
        new_family_wildcards = dict(family_wildcards)
        new_family_wildcards[character] = family
        effectively_parsed = parsed
        if currently_parsed:
            effectively_parsed += currently_parsed + family.value
        leftover = to_parse[idx + 1:]
        if global_wildcard_parse:
            leftover = global_wildcard_parse + family.value + leftover
        iterators.append(_pattern_generator(effectively_parsed,
                                         leftover, new_family_wildcards, number_wildcards))
    return iterators


def _pattern_generator(parsed: str, to_parse: str, family_wildcards: dict[str, Family],
                       number_wildcards: dict[str, int]) -> Iterator[str]:
    currently_parsed = ""
    global_wildcard_parse = ""

    for idx, character in enumerate(to_parse):
        if character in "123456789":
            currently_parsed += character
        elif character in Family:
            if global_wildcard_parse:
                for iterator in _pattern_resolve_number_wildcards(parsed, to_parse, family_wildcards, number_wildcards,
                                                                  global_wildcard_parse, idx, character):
                    for result in iterator:
                        yield result
                return
            currently_parsed += character
        elif character.isupper():
            global_wildcard_parse += character
        elif character.islower():
            for iterator in _pattern_resolve_family_wildcard(parsed, to_parse, family_wildcards, number_wildcards,
                                                             currently_parsed, global_wildcard_parse, idx, character):
                for result in iterator:
                    yield result
            return
        else:
            raise AttributeError('Misplaced or unknown character')

    if parsed + currently_parsed:
        yield parsed + currently_parsed

if __name__ == "__main__":
    #for pattern in pattern_generator('123w456x789y'):
    #    print(pattern)
    #for pattern in pattern_generator('ABCCDEEFGs'):
    #    print(pattern)
    #for pattern in pattern_generator('ABCsBCDpCDEm'):
    #    print(pattern)
    #for pattern in pattern_generator('ABCwBCDxCDEy'):
    #    print(pattern)
    for pattern in pattern_generator('ABCaCDEaEFGa'):
        print(pattern)
