# Python 代码规范

## 一、Docstring 基本原则

1. 所有**公共函数、方法、类、模块**必须包含 docstring。
2. 使用 **Google 风格**（即 `Args:`、`Returns:`、`Raises:` 等分节）。
3. 类型信息**优先使用 type hints**，docstring 中不再重复类型，除非特别强调或复杂泛型需要说明。
4. docstring 必须准确描述**功能、参数、返回值、异常、副作用**，并包含**可运行的示例**（如果可能）。
5. 语言简洁、客观，使用**中文**。

## 二、模块级 docstring

```python
"""模块功能的一句话概述。

如果有必要，可以在此处扩展详细描述模块职责、主要包含的类或函数，
以及使用时需要注意的前置条件。

Example:
    典型的使用场景示例代码（可选）：
    >>> from module import SomeClass
    >>> obj = SomeClass()
    >>> obj.method()
"""
```

## 三、类级 docstring

```python
class MyClass:
    """类的一句话概述。

    详细描述类的职责、设计思路、生命周期，以及与其它类的协作关系。
    
    Attributes:
        attr1: 属性含义。
        attr2: 属性含义，默认值及作用。
    """

    def __init__(self, param1: str, param2: int = 0) -> None:
        """
        Args:
            param1: 参数含义。
            param2: 参数含义，默认0，表示不超时。
        """
        self.attr1 = param1
        self.attr2 = param2
```

要求：`Attributes:` 部分列出所有公开属性（包括通过 property 暴露的）。属性类型由 type hints 表达，文档中不再重复写 `(str)` 之类。

## 四、函数/方法 docstring 核心模板

```python
def function_name(arg1: Type1, arg2: Type2 = default) -> ReturnType:
    """执行功能的简短说明（一行）。

    详细描述，可以跨多行。说明该函数的行为、算法概要、重要约定、
    前置条件和后置条件。

    Args:
        arg1: 参数1的含义，必须包含约束（如取值范围、格式）。
        arg2: 参数2的含义，默认值的含义。

    Returns:
        返回值的含义，如果是复杂结构，需说明结构组成。
        如果返回 None，写 "None: 无返回值"。

    Raises:
        ValueError: 在什么情况下抛出。
        IOError: 在什么情况下抛出。

    Example:
        >>> result = function_name("test", 5)
        >>> print(result)
        预期输出
    """
```

必须遵守：
- `Args:` 中每个参数一行，格式为 `参数名: 说明`。
- `Returns:` 中说明返回值内容，即使 type hint 已标明类型，仍需用文字解释**含义**。
- `Raises:` 列出可能显式抛出的异常，并解释条件。
- `Example:` 中的代码必须是可以直接运行的，避免使用 `...` 占位符，展示真实调用和输出。

## 五、特殊情况

多返回值：说明每个元素含义。生成器：用 `Yields:` 替代 `Returns:`。异步函数、装饰器同样需编写 docstring。

## 六、禁止的做法

- 使用过时的 Sphinx 标签如 `:param str name:`，必须用 Google 风格 `Args:`。
- 在 docstring 中简单重复函数名或参数名。
- 提供无法执行的虚假示例。
- 忽略异常，只要函数可能 raise 就必须在 `Raises:` 中注明。
- 对内部私有函数（以 `_` 开头）写完整 docstring（可简写一行描述，不必分节）。

## 七、代码注释

为函数内关键操作代码编写行内注释，注明其功能、作用或目的，注释均使用简体中文，简洁精炼。

## 八、代码质量检查

- 变量类型不匹配：检查变量赋值时的类型兼容性，特别是 Optional 类型与非 Optional 类型之间的赋值
- 函数返回值类型检查：验证函数实际返回值与声明的返回类型是否一致
- 函数参数类型检查：确保函数调用时传入的参数类型与函数签名匹配
- 类属性类型检查：验证类属性的类型注解与实际使用是否一致
- 版本弃用类型检查：检查使用了已弃用的 Python 版本特性，避免在新代码中使用
- 类型注释完整性检查：确保所有函数、方法和类的参数、返回值和属性都有类型注释